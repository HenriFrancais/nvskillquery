"""The committed demo fixtures conform to the upstream contract and build a
usable snapshot."""

from __future__ import annotations

import json
from pathlib import Path

from app.sde.catalog import SdeCatalog
from app.snapshot.build import build_snapshot
from app.snapshot.models import SkillDef
from app.sources.payloads import SkillPrereq, SkillsApiPayload, UsersApiPayload

DATA_DEMO = Path(__file__).resolve().parent.parent / "data_demo"


def _demo_catalog() -> SdeCatalog:
    data = json.loads((DATA_DEMO / "sde_skills.json").read_text())
    return SdeCatalog(
        build_number=data["sde_build_number"],
        skills={
            s["skill_id"]: SkillDef(
                skill_id=s["skill_id"],
                name=s["name"],
                group_id=s["group_id"],
                group_name=s["group_name"],
                prerequisites=tuple(
                    SkillPrereq(skill_id=p["skill_id"], level=p["level"])
                    for p in s["prerequisites"]
                ),
            )
            for s in data["skills"]
        },
    )


def test_demo_fixtures_parse_and_build():
    skills = SkillsApiPayload.model_validate(
        json.loads((DATA_DEMO / "skills_api.json").read_text())
    )
    users = UsersApiPayload.model_validate(
        json.loads((DATA_DEMO / "users_api.json").read_text())
    )
    catalog = _demo_catalog()
    snap = build_snapshot(skills, users, catalog=catalog, version=1, fetched_at=0.0)
    assert len(snap.skills) == len(catalog.skills) >= 50
    assert len(snap.users) == 50
    assert len(snap.characters) >= 100
    assert snap.character_groups == ("All",)
    assert snap.sde_build_number == catalog.build_number > 0
    # Trained skills reference the catalogue (real SDE ids) — nothing dropped.
    assert all(
        sid in snap.skills
        for c in snap.characters.values()
        for sid in c.skill_levels
    )
    # Every user's first character is their main.
    for user in snap.users.values():
        assert snap.characters[user.character_ids[0]].is_main
    # Some prereq chains exist in the catalogue.
    assert any(s.prerequisites for s in snap.skills.values())
    # Every character carries a known group.
    assert {c.group for c in snap.characters.values()} == {"All"}
