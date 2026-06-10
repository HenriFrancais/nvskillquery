"""Builders for small inline domain objects used across the pure-logic tests."""

from __future__ import annotations

from app.sde.catalog import SdeCatalog
from app.snapshot.build import build_snapshot
from app.snapshot.models import CharacterRecord, SkillDef, Snapshot
from app.sources.payloads import SkillPrereq, SkillsApiPayload, UsersApiPayload

GENERATED_AT = "2026-01-01T00:00:00Z"


def char(
    character_id: int = 1,
    group: str = "Home",
    skill_levels: dict[int, int] | None = None,
    user_id: int = 1,
    is_main: bool = True,
    name: str = "Pilot",
) -> CharacterRecord:
    return CharacterRecord(
        character_id=character_id,
        name=name,
        group=group,
        user_id=user_id,
        is_main=is_main,
        skill_levels=skill_levels or {},
    )


def catalog_from(skills: list[dict], build_number: int = 1) -> SdeCatalog:
    """SdeCatalog from dicts in the artifact shape."""
    return SdeCatalog(
        build_number=build_number,
        skills={
            s["skill_id"]: SkillDef(
                skill_id=s["skill_id"],
                name=s["name"],
                group_id=s["group_id"],
                group_name=s["group_name"],
                prerequisites=tuple(
                    SkillPrereq(skill_id=p["skill_id"], level=p["level"])
                    for p in s.get("prerequisites", [])
                ),
            )
            for s in skills
        },
    )


def snapshot_from(
    catalog_skills: list[dict],
    trained: dict,
    users: dict,
    version: int = 1,
    fetched_at: float = 0.0,
) -> Snapshot:
    """Build a snapshot from raw payload dicts (validated through the
    upstream models, same as production) plus an SDE catalogue."""
    return build_snapshot(
        SkillsApiPayload.model_validate({"generated_at": GENERATED_AT, **trained}),
        UsersApiPayload.model_validate({"generated_at": GENERATED_AT, **users}),
        catalog=catalog_from(catalog_skills),
        version=version,
        fetched_at=fetched_at,
    )


CATALOG_SKILLS = [
    {"skill_id": 1, "name": "Skill One", "group_id": 10, "group_name": "G1",
     "prerequisites": []},
    {"skill_id": 2, "name": "Skill Two", "group_id": 10, "group_name": "G1",
     "prerequisites": [{"skill_id": 1, "level": 3}]},
]


def simple_snapshot() -> Snapshot:
    """Three users / five characters / two skills — covers mains, alts,
    zero-match users, and the group pool.

    - Alice: main Alice (Home, skill 1 @5), alt Alice II (Strat, skill 1 @3, skill 2 @4)
    - Bob: main Bob (Home, skill 2 @2)
    - Carol: main Carol (Farm, no skills), alt Carol II (Home, skill 1 @4)
    """
    return snapshot_from(
        CATALOG_SKILLS,
        {
            "users": [
                {"user_id": 1, "characters": [
                    {"character_id": 101, "skills": [{"skill_id": 1, "level": 5}]},
                    {"character_id": 102, "skills": [{"skill_id": 1, "level": 3},
                                                     {"skill_id": 2, "level": 4}]},
                ]},
                {"user_id": 2, "characters": [
                    {"character_id": 201, "skills": [{"skill_id": 2, "level": 2}]},
                ]},
                {"user_id": 3, "characters": [
                    {"character_id": 301, "skills": []},
                    {"character_id": 302, "skills": [{"skill_id": 1, "level": 4}]},
                ]},
            ],
        },
        {
            "character_groups": ["Home", "Strat", "Farm", "Alpha"],
            "users": [
                {"user_id": 1, "user_name": "Alice", "main_character_id": 101, "characters": [
                    {"character_id": 101, "name": "Alice", "group": "Home"},
                    {"character_id": 102, "name": "Alice II", "group": "Strat"},
                ]},
                {"user_id": 2, "user_name": "Bob", "main_character_id": 201, "characters": [
                    {"character_id": 201, "name": "Bob", "group": "Home"},
                ]},
                {"user_id": 3, "user_name": "Carol", "main_character_id": 301, "characters": [
                    {"character_id": 301, "name": "Carol", "group": "Farm"},
                    {"character_id": 302, "name": "Carol II", "group": "Home"},
                ]},
            ],
        },
    )
