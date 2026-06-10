"""Process-wide snapshot store with stale-while-revalidate semantics
(pattern: router's PresenceCache).

  - fresh (age < TTL): return cached snapshot, no fetch.
  - stale + present: return cached snapshot, kick off a background refresh.
  - cold (no snapshot yet): block on the fetch (first request after boot).

The app warms the store from the lifespan via ``asyncio.create_task`` so the
first user-facing query doesn't pay the cold cost. The version counter bumps
only on successful refresh; a failed refresh keeps serving the old snapshot.
"""

from __future__ import annotations

import asyncio
import time

from app.config import Settings
from app.observability.health import HEALTH
from app.observability.logging import log
from app.snapshot.build import build_snapshot
from app.snapshot.models import Snapshot
from app.sources.base import DataSource


class SnapshotStore:
    def __init__(self, settings: Settings, source: DataSource) -> None:
        self._settings = settings
        self._source = source
        self._state: Snapshot | None = None
        self._version = 0
        self._expires_at = 0.0
        self._lock = asyncio.Lock()
        self._inflight: asyncio.Task[Snapshot] | None = None

    @property
    def has_state(self) -> bool:
        return self._state is not None

    async def get(self) -> Snapshot:
        now = time.monotonic()
        if self._state is not None and now < self._expires_at:
            return self._state
        if self._state is not None:
            # Stale: serve immediately, refresh in the background.
            self._schedule_refresh()
            return self._state
        # Cold: must block.
        return await self._cold_fetch()

    async def _cold_fetch(self) -> Snapshot:
        async with self._lock:
            if self._state is not None:
                # Lost the race; another caller just populated it.
                return self._state
            snap = await self._fetch()
            self._set_state(snap)
            return snap

    def _schedule_refresh(self) -> None:
        if self._inflight is not None and not self._inflight.done():
            return
        self._inflight = asyncio.create_task(self._background_refresh())

    async def _background_refresh(self) -> Snapshot:
        try:
            snap = await self._fetch()
            self._set_state(snap)
            return snap
        except Exception as exc:
            log.warning("snapshot.refresh_failed", error=str(exc))
            assert self._state is not None  # only scheduled when state exists
            # Push the next retry a TTL out so a dead upstream isn't hammered
            # on every request.
            self._expires_at = time.monotonic() + self._settings.snapshot_ttl_s
            return self._state

    def _set_state(self, snap: Snapshot) -> None:
        self._state = snap
        self._version = snap.version
        self._expires_at = time.monotonic() + self._settings.snapshot_ttl_s
        HEALTH.snapshot_loaded = True
        HEALTH.snapshot_version = snap.version
        HEALTH.snapshot_fetched_at = snap.fetched_at

    async def _fetch(self) -> Snapshot:
        from app.sde.catalog import get_sde_catalog

        skills, users = await asyncio.gather(
            self._source.fetch_skills(), self._source.fetch_users()
        )
        snap = build_snapshot(
            skills,
            users,
            catalog=get_sde_catalog(),
            version=self._version + 1,
            fetched_at=time.time(),
        )
        log.info(
            "snapshot.fetched",
            version=snap.version,
            users=len(snap.users),
            characters=len(snap.characters),
            skills=len(snap.skills),
        )
        return snap


_singleton: SnapshotStore | None = None


def get_snapshot_store(settings: Settings) -> SnapshotStore:
    global _singleton
    if _singleton is None:
        from app.sources.factory import get_data_source

        _singleton = SnapshotStore(settings, get_data_source(settings))
    return _singleton


def reset_snapshot_store_for_tests() -> None:
    global _singleton
    _singleton = None
