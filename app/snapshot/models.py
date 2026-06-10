"""In-memory snapshot of the joined upstream data.

This is the entire data layer — there is no database. A new immutable
Snapshot replaces the old one on every successful refresh; the version
counter keys the query-result LRU so invalidation is implicit.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.sources.payloads import SkillPrereq


@dataclass(slots=True, frozen=True)
class SkillDef:
    skill_id: int
    name: str
    group_id: int
    group_name: str
    prerequisites: tuple[SkillPrereq, ...]


@dataclass(slots=True, frozen=True)
class CharacterRecord:
    character_id: int
    name: str
    # Pool group (e.g. Home/Strat/Farm/Alpha) — scopes which characters a
    # query considers; never a query condition itself.
    group: str
    user_id: int
    is_main: bool
    # skill_id → trained level; absent = untrained. The evaluation index:
    # every query leaf is one O(1) lookup here.
    skill_levels: dict[int, int]


@dataclass(slots=True, frozen=True)
class UserRecord:
    user_id: int
    user_name: str
    main_character_id: int
    # Main first, then alts by name — precomputed display order.
    character_ids: tuple[int, ...]


@dataclass(slots=True, frozen=True)
class Snapshot:
    version: int
    fetched_at: float  # epoch seconds
    # The skill catalogue comes from the processed SDE artifact, not upstream.
    sde_build_number: int
    skills: dict[int, SkillDef]
    character_groups: tuple[str, ...]
    users: dict[int, UserRecord]
    characters: dict[int, CharacterRecord]
    # user_ids sorted by user_name — stable result ordering.
    users_sorted: tuple[int, ...]
