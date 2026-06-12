"""SnapshotStore stale-while-revalidate behaviour with a controllable fake
source."""

from __future__ import annotations

import asyncio

import pytest

from app.config import Settings
from app.sde.catalog import SdeCatalog
from app.snapshot.store import SnapshotStore
from app.sources.payloads import (
    DoctrinesApiPayload,
    SkillsApiPayload,
    UsersApiPayload,
)


@pytest.fixture(autouse=True)
def _stub_sde_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.sde import catalog as sde_catalog

    stub = SdeCatalog(build_number=1, skills={})
    monkeypatch.setattr(sde_catalog, "get_sde_catalog", lambda: stub)


class FakeSource:
    name = "fake"

    def __init__(self) -> None:
        self.fetches = 0
        self.fail = False

    async def fetch_skills(self) -> SkillsApiPayload:
        self.fetches += 1
        if self.fail:
            raise RuntimeError("upstream down")
        return SkillsApiPayload.model_validate([])

    async def fetch_users(self) -> UsersApiPayload:
        return UsersApiPayload.model_validate(
            [
                {
                    "user_name": "Alice",
                    "main_character_id": 101,
                    "characters": [
                        {"character_id": 101, "character_name": "Alice"}
                    ],
                }
            ]
        )

    async def fetch_doctrines(self) -> DoctrinesApiPayload:
        return DoctrinesApiPayload.model_validate([])


def make_store(ttl: float = 1000.0) -> tuple[SnapshotStore, FakeSource]:
    settings = Settings(snapshot_ttl_s=ttl, _env_file=None)
    source = FakeSource()
    return SnapshotStore(settings, source), source


async def test_cold_get_blocks_and_fetches():
    store, source = make_store()
    assert not store.has_state
    snap = await store.get()
    assert snap.version == 1
    assert source.fetches == 1


async def test_fresh_get_serves_cache_without_fetch():
    store, source = make_store()
    await store.get()
    snap = await store.get()
    assert snap.version == 1
    assert source.fetches == 1


async def test_stale_get_serves_old_then_refreshes(monkeypatch):
    store, source = make_store(ttl=0.0)  # everything is immediately stale
    first = await store.get()
    assert first.version == 1
    second = await store.get()  # stale: serves v1, schedules background refresh
    assert second.version == 1
    await asyncio.sleep(0)  # let the refresh task run
    assert store._inflight is not None
    await store._inflight
    third = await store.get()
    assert third.version >= 2
    assert source.fetches >= 2


async def test_failed_refresh_keeps_old_snapshot():
    store, source = make_store(ttl=0.0)
    await store.get()
    source.fail = True
    snap = await store.get()  # schedules a refresh that will fail
    assert snap.version == 1
    await store._inflight
    after = await store.get()
    assert after.version == 1  # old snapshot retained, version unchanged
    assert store.has_state


async def test_cold_fetch_failure_propagates():
    store, source = make_store()
    source.fail = True
    with pytest.raises(RuntimeError):
        await store.get()
    assert not store.has_state


async def test_concurrent_cold_gets_fetch_once():
    store, source = make_store()
    snaps = await asyncio.gather(*(store.get() for _ in range(5)))
    assert {s.version for s in snaps} == {1}
    assert source.fetches == 1
