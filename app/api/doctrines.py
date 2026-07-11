"""Doctrine catalogue endpoint: the cascading-selector vocabulary the UI needs
to pick a fit (doctrine → role → ship_type → fit_name) plus the per-tier skill
counts. The skill lists themselves stay server-side — the backend expands a
selected fit at query time."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.auth import require_access
from app.api.query import get_snapshot_or_503
from app.queries.doctrine import fit_skill_counts
from app.snapshot.models import Snapshot

router = APIRouter(dependencies=[Depends(require_access)])


class DoctrineFitOut(BaseModel):
    doctrine: str
    role: str
    ship_type: str
    fit_name: str
    yellow_skill_count: int
    green_skill_count: int


class DoctrinesResponse(BaseModel):
    fits: list[DoctrineFitOut]
    snapshot_version: int
    snapshot_fetched_at: str


def _doctrines_from(snapshot: Snapshot) -> DoctrinesResponse:
    fits = []
    for fit in snapshot.doctrines:  # already sorted by identity tuple
        yellow, green = fit_skill_counts(fit)
        fits.append(
            DoctrineFitOut(
                doctrine=fit.doctrine,
                role=fit.role,
                ship_type=fit.ship_type,
                fit_name=fit.fit_name,
                yellow_skill_count=yellow,
                green_skill_count=green,
            )
        )
    return DoctrinesResponse(
        fits=fits,
        snapshot_version=snapshot.version,
        snapshot_fetched_at=datetime.fromtimestamp(snapshot.fetched_at, tz=UTC).isoformat(),
    )


@router.get("/api/doctrines")
async def doctrines() -> DoctrinesResponse:
    return _doctrines_from(await get_snapshot_or_503())
