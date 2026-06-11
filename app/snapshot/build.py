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

# Real users API carries no per-character group, so the pool filter is inert:
# every character lands in this single default group.
DEFAULT_GROUP = "All"


def build_snapshot(
    skills_payload: SkillsApiPayload,
    users_payload: UsersApiPayload,
    catalog: SdeCatalog,
    version: int,
    fetched_at: float,
) -> Snapshot:
    users_in = users_payload.root
    skills_in = skills_payload.root

    known_character_ids = {c.character_id for u in users_in for c in u.characters}

    # character_id -> {skill_id: level}, joined on character_id.
    trained: dict[int, dict[int, int]] = {}
    unknown_skill_ids: set[int] = set()
    for entry in skills_in:
        if entry.character_id not in known_character_ids:
            log.warning("snapshot.orphan_character", character_id=entry.character_id)
            continue
        levels: dict[int, int] = {}
        for skill_id, level in entry.skills.items():
            if skill_id not in catalog.skills:
                if skill_id not in unknown_skill_ids:
                    unknown_skill_ids.add(skill_id)
                    log.warning("snapshot.unknown_skill", skill_id=skill_id)
                continue
            levels[skill_id] = level
        trained[entry.character_id] = levels

    users: dict[int, UserRecord] = {}
    characters: dict[int, CharacterRecord] = {}
    for user in users_in:
        if not user.characters:
            log.warning("snapshot.user_without_characters", user_name=user.user_name)
            continue
        char_ids = {c.character_id for c in user.characters}
        main_id = user.main_character_id
        if main_id not in char_ids:
            log.warning(
                "snapshot.main_not_in_characters",
                user_name=user.user_name,
                main_character_id=main_id,
            )
            main_id = user.characters[0].character_id
        # The user's stable int identity is its main character id.
        user_id = main_id
        if user_id in users:
            # Two users resolving to the same main id would silently clobber
            # each other; surface it like the other integrity violations.
            log.warning("snapshot.duplicate_user_key", user_name=user.user_name, user_id=user_id)
            continue
        alts = sorted(
            (c for c in user.characters if c.character_id != main_id),
            key=lambda c: c.character_name,
        )
        ordered = [next(c for c in user.characters if c.character_id == main_id), *alts]
        for c in ordered:
            characters[c.character_id] = CharacterRecord(
                character_id=c.character_id,
                name=c.character_name,
                group=DEFAULT_GROUP,
                user_id=user_id,
                is_main=c.character_id == main_id,
                skill_levels=trained.get(c.character_id, {}),
            )
        users[user_id] = UserRecord(
            user_id=user_id,
            user_name=user.user_name,
            main_character_id=main_id,
            character_ids=tuple(c.character_id for c in ordered),
        )

    return Snapshot(
        version=version,
        fetched_at=fetched_at,
        sde_build_number=catalog.build_number,
        skills=catalog.skills,
        character_groups=(DEFAULT_GROUP,),
        users=users,
        characters=characters,
        users_sorted=tuple(sorted(users, key=lambda uid: users[uid].user_name)),
    )
