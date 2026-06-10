"""Deeper /healthz endpoint exposing snapshot state for uptime probes."""

from __future__ import annotations

import time

from fastapi import APIRouter

router = APIRouter()


# Process-singleton health state; the snapshot store writes to these as data
# comes online.
class HealthState:
    snapshot_loaded: bool = False
    snapshot_version: int = 0
    snapshot_fetched_at: float = 0.0
    data_source: str = ""


HEALTH = HealthState()


@router.get("/healthz")
async def healthz() -> dict[str, object]:
    now = time.time()
    age = now - HEALTH.snapshot_fetched_at if HEALTH.snapshot_fetched_at else None
    return {
        "ok": True,
        "snapshot_loaded": HEALTH.snapshot_loaded,
        "snapshot_version": HEALTH.snapshot_version,
        "snapshot_age_s": age,
        "data_source": HEALTH.data_source,
    }
