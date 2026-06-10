"""The committed demo fixtures conform to the upstream contract and build a
usable snapshot."""

from __future__ import annotations

import json
from pathlib import Path

from app.snapshot.build import build_snapshot
from app.sources.payloads import SkillsApiPayload, UsersApiPayload

DATA_DEMO = Path(__file__).resolve().parent.parent / "data_demo"


def test_demo_fixtures_parse_and_build():
    skills = SkillsApiPayload.model_validate(
        json.loads((DATA_DEMO / "skills_api.json").read_text())
    )
    users = UsersApiPayload.model_validate(
        json.loads((DATA_DEMO / "users_api.json").read_text())
    )
    snap = build_snapshot(skills, users, version=1, fetched_at=0.0)
    assert len(snap.skills) == 80
    assert len(snap.users) == 50
    assert len(snap.characters) >= 100
    assert len(snap.char_types) == 8
    # Every user's first character is their main.
    for user in snap.users.values():
        assert snap.characters[user.character_ids[0]].is_main
    # Some prereq chains exist in the catalogue.
    assert any(s.prerequisites for s in snap.skills.values())
