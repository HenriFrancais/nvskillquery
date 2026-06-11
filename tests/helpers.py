"""Builders for small inline domain objects used across the pure-logic tests."""

from __future__ import annotations

from app.sde.catalog import SdeCatalog
from app.snapshot.build import build_snapshot
from app.snapshot.models import CharacterRecord, SkillDef, Snapshot, UserRecord
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
    zero-match users, and a multi-group pool. Built directly (not through
    build_snapshot) because the real upstream payload no longer carries
    per-character groups; the pool-filter logic itself is group-agnostic and
    is still exercised here.

    - Alice: main Alice (Home, skill 1 @5), alt Alice II (Strat, skill 1 @3, skill 2 @4)
    - Bob: main Bob (Home, skill 2 @2)
    - Carol: main Carol (Farm, no skills), alt Carol II (Home, skill 1 @4)
    """
    catalog = catalog_from(CATALOG_SKILLS)
    characters = {
        101: CharacterRecord(character_id=101, name="Alice", group="Home",
                             user_id=1, is_main=True, skill_levels={1: 5}),
        102: CharacterRecord(character_id=102, name="Alice II", group="Strat",
                             user_id=1, is_main=False, skill_levels={1: 3, 2: 4}),
        201: CharacterRecord(character_id=201, name="Bob", group="Home",
                             user_id=2, is_main=True, skill_levels={2: 2}),
        301: CharacterRecord(character_id=301, name="Carol", group="Farm",
                             user_id=3, is_main=True, skill_levels={}),
        302: CharacterRecord(character_id=302, name="Carol II", group="Home",
                             user_id=3, is_main=False, skill_levels={1: 4}),
    }
    users = {
        1: UserRecord(user_id=1, user_name="Alice", main_character_id=101,
                      character_ids=(101, 102)),
        2: UserRecord(user_id=2, user_name="Bob", main_character_id=201,
                      character_ids=(201,)),
        3: UserRecord(user_id=3, user_name="Carol", main_character_id=301,
                      character_ids=(301, 302)),
    }
    return Snapshot(
        version=1,
        fetched_at=0.0,
        sde_build_number=catalog.build_number,
        skills=catalog.skills,
        character_groups=("Home", "Strat", "Farm", "Alpha"),
        users=users,
        characters=characters,
        users_sorted=tuple(sorted(users, key=lambda uid: users[uid].user_name)),
    )
