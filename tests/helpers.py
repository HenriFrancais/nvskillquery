"""Builders for small inline domain objects used across the pure-logic tests."""

from __future__ import annotations

from app.snapshot.build import build_snapshot
from app.snapshot.models import CharacterRecord, Snapshot
from app.sources.payloads import SkillsApiPayload, UsersApiPayload

GENERATED_AT = "2026-01-01T00:00:00Z"


def char(
    character_id: int = 1,
    character_type: str = "Subcap",
    skill_levels: dict[int, int] | None = None,
    user_id: int = 1,
    is_main: bool = True,
    name: str = "Pilot",
) -> CharacterRecord:
    return CharacterRecord(
        character_id=character_id,
        name=name,
        character_type=character_type,
        user_id=user_id,
        is_main=is_main,
        skill_levels=skill_levels or {},
    )


def snapshot_from(skills: dict, users: dict, version: int = 1, fetched_at: float = 0.0) -> Snapshot:
    """Build a snapshot from raw payload dicts (validated through the
    upstream models, same as production)."""
    return build_snapshot(
        SkillsApiPayload.model_validate({"generated_at": GENERATED_AT, **skills}),
        UsersApiPayload.model_validate({"generated_at": GENERATED_AT, **users}),
        version=version,
        fetched_at=fetched_at,
    )


def simple_snapshot() -> Snapshot:
    """Three users / five characters / two skills — covers mains, alts,
    zero-match users, and both condition kinds.

    - Alice: main Alice (Subcap, skill 1 @5), alt Alice II (Dreadnought, skill 1 @3, skill 2 @4)
    - Bob: main Bob (Subcap, skill 2 @2)
    - Carol: main Carol (Carrier, no skills), alt Carol II (Subcap, skill 1 @4)
    """
    return snapshot_from(
        {
            "skills": [
                {"skill_id": 1, "name": "Skill One", "group_id": 10, "group_name": "G1",
                 "prerequisites": []},
                {"skill_id": 2, "name": "Skill Two", "group_id": 10, "group_name": "G1",
                 "prerequisites": [{"skill_id": 1, "level": 3}]},
            ],
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
            "character_types": ["Subcap", "Dreadnought", "Carrier"],
            "users": [
                {"user_id": 1, "user_name": "Alice", "main_character_id": 101, "characters": [
                    {"character_id": 101, "name": "Alice", "character_type": "Subcap"},
                    {"character_id": 102, "name": "Alice II", "character_type": "Dreadnought"},
                ]},
                {"user_id": 2, "user_name": "Bob", "main_character_id": 201, "characters": [
                    {"character_id": 201, "name": "Bob", "character_type": "Subcap"},
                ]},
                {"user_id": 3, "user_name": "Carol", "main_character_id": 301, "characters": [
                    {"character_id": 301, "name": "Carol", "character_type": "Carrier"},
                    {"character_id": 302, "name": "Carol II", "character_type": "Subcap"},
                ]},
            ],
        },
    )
