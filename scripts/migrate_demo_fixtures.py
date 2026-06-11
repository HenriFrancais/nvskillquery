"""One-shot: rewrite data_demo/{skills,users}_api.json from the old proposed
contract into the real NV API shapes. Network-free and deterministic — reads
the committed fixtures and rewrites them. Run exactly once on the old-shape
files; re-running on already-migrated files will fail.

    uv run python scripts/migrate_demo_fixtures.py
"""

from __future__ import annotations

import json
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "data_demo"


def main() -> None:
    old_users = json.loads((OUT_DIR / "users_api.json").read_text())
    old_skills = json.loads((OUT_DIR / "skills_api.json").read_text())

    # character_id -> main_character_id, from the users fixture.
    main_of: dict[int, int] = {}
    for u in old_users["users"]:
        for c in u["characters"]:
            main_of[c["character_id"]] = u["main_character_id"]

    new_users = [
        {
            "user_name": u["user_name"],
            "main_character_id": u["main_character_id"],
            "characters": [
                {"character_id": c["character_id"], "character_name": c["name"]}
                for c in u["characters"]
            ],
            "discord_id": None,
            "rank": "Member",
            "teams": [],
            "allowed_apps": ["skillquery"],
        }
        for u in old_users["users"]
    ]

    new_skills = [
        {
            "character_id": c["character_id"],
            "main_character_id": main_of[c["character_id"]],
            "skills": {str(s["skill_id"]): s["level"] for s in c["skills"]},
        }
        for u in old_skills["users"]
        for c in u["characters"]
    ]

    (OUT_DIR / "users_api.json").write_text(json.dumps(new_users, indent=2) + "\n")
    (OUT_DIR / "skills_api.json").write_text(json.dumps(new_skills, indent=2) + "\n")
    print(f"migrated {len(new_users)} users, {len(new_skills)} character skill entries")


if __name__ == "__main__":
    main()
