"""Catalog endpoint: everything the query builder UI needs to render its
pickers — skills grouped by skill group (with prerequisite names resolved
server-side so the UI needs no join) and the character-type vocabulary."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.auth import require_skills
from app.api.query import get_snapshot_or_503
from app.snapshot.models import Snapshot

router = APIRouter(dependencies=[Depends(require_skills)])


class PrereqOut(BaseModel):
    skill_id: int
    name: str
    level: int


class SkillOut(BaseModel):
    skill_id: int
    name: str
    group_id: int
    group_name: str
    prerequisites: list[PrereqOut]


class GroupOut(BaseModel):
    group_id: int
    name: str


class CatalogResponse(BaseModel):
    skills: list[SkillOut]
    groups: list[GroupOut]
    char_types: list[str]
    snapshot_version: int
    snapshot_fetched_at: str


def _catalog_from(snapshot: Snapshot) -> CatalogResponse:
    skills = sorted(snapshot.skills.values(), key=lambda s: (s.group_name, s.name))
    groups_seen: dict[int, str] = {}
    out_skills: list[SkillOut] = []
    for s in skills:
        groups_seen.setdefault(s.group_id, s.group_name)
        out_skills.append(
            SkillOut(
                skill_id=s.skill_id,
                name=s.name,
                group_id=s.group_id,
                group_name=s.group_name,
                prerequisites=[
                    PrereqOut(
                        skill_id=p.skill_id,
                        name=(
                            snapshot.skills[p.skill_id].name
                            if p.skill_id in snapshot.skills
                            else f"#{p.skill_id}"
                        ),
                        level=p.level,
                    )
                    for p in s.prerequisites
                ],
            )
        )
    return CatalogResponse(
        skills=out_skills,
        groups=[
            GroupOut(group_id=gid, name=name)
            for gid, name in sorted(groups_seen.items(), key=lambda kv: kv[1])
        ],
        char_types=list(snapshot.char_types),
        snapshot_version=snapshot.version,
        snapshot_fetched_at=datetime.fromtimestamp(
            snapshot.fetched_at, tz=UTC
        ).isoformat(),
    )


@router.get("/api/catalog")
async def catalog() -> CatalogResponse:
    return _catalog_from(await get_snapshot_or_503())
