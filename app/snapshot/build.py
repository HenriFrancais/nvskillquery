"""Join the two upstream payloads + the SDE catalogue into an immutable Snapshot.

Pure function — no I/O, no clocks beyond the caller-supplied fetched_at —
so the reconciliation rules in docs/upstream-api.md are unit-testable in
isolation. The users API is authoritative for which users/characters exist;
the skills API only contributes trained levels; the skill catalogue comes
from the processed SDE artifact.
"""

from __future__ import annotations

from app.observability.logging import log
from app.sde.catalog import SdeCatalog
from app.snapshot.models import CharacterRecord, Snapshot, UserRecord
from app.sources.payloads import SkillsApiPayload, UsersApiPayload


def build_snapshot(
    skills_payload: SkillsApiPayload,
    users_payload: UsersApiPayload,
    catalog: SdeCatalog,
    version: int,
    fetched_at: float,
) -> Snapshot:
    # character_id → {skill_id: level} from the skills payload.
    trained: dict[int, dict[int, int]] = {}
    known_character_ids = {
        c.character_id for u in users_payload.users for c in u.characters
    }
    known_user_ids = {u.user_id for u in users_payload.users}
    unknown_skill_ids: set[int] = set()
    for skills_user in skills_payload.users:
        if skills_user.user_id not in known_user_ids:
            log.warning("snapshot.orphan_user", user_id=skills_user.user_id)
            continue
        for char in skills_user.characters:
            if char.character_id not in known_character_ids:
                log.warning(
                    "snapshot.orphan_character",
                    user_id=skills_user.user_id,
                    character_id=char.character_id,
                )
                continue
            levels: dict[int, int] = {}
            for s in char.skills:
                if s.skill_id not in catalog.skills:
                    # Upstream knows a skill the SDE doesn't — drop it (warn
                    # once per id, not per character).
                    if s.skill_id not in unknown_skill_ids:
                        unknown_skill_ids.add(s.skill_id)
                        log.warning("snapshot.unknown_skill", skill_id=s.skill_id)
                    continue
                levels[s.skill_id] = s.level
            trained[char.character_id] = levels

    users: dict[int, UserRecord] = {}
    characters: dict[int, CharacterRecord] = {}
    for user in users_payload.users:
        if not user.characters:
            log.warning("snapshot.user_without_characters", user_id=user.user_id)
            continue
        char_ids = {c.character_id for c in user.characters}
        main_id = user.main_character_id
        if main_id not in char_ids:
            log.warning(
                "snapshot.main_not_in_characters",
                user_id=user.user_id,
                main_character_id=main_id,
            )
            main_id = user.characters[0].character_id
        alts = sorted(
            (c for c in user.characters if c.character_id != main_id),
            key=lambda c: c.name,
        )
        ordered = [next(c for c in user.characters if c.character_id == main_id), *alts]
        for c in ordered:
            characters[c.character_id] = CharacterRecord(
                character_id=c.character_id,
                name=c.name,
                group=c.group,
                user_id=user.user_id,
                is_main=c.character_id == main_id,
                skill_levels=trained.get(c.character_id, {}),
            )
        users[user.user_id] = UserRecord(
            user_id=user.user_id,
            user_name=user.user_name,
            main_character_id=main_id,
            character_ids=tuple(c.character_id for c in ordered),
        )

    character_groups = tuple(users_payload.character_groups) or tuple(
        sorted({c.group for c in characters.values()})
    )

    return Snapshot(
        version=version,
        fetched_at=fetched_at,
        sde_build_number=catalog.build_number,
        skills=catalog.skills,
        character_groups=character_groups,
        users=users,
        characters=characters,
        users_sorted=tuple(sorted(users, key=lambda uid: users[uid].user_name)),
    )
