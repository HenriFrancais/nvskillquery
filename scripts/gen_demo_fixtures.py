"""Generate deterministic demo fixtures conforming to docs/upstream-api.md.

Run once and commit the output; tests and DATA_SOURCE=demo deployments read
the committed files:

    uv run python scripts/gen_demo_fixtures.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "data_demo"
GENERATED_AT = "2026-01-01T00:00:00Z"
SEED = 1337

GROUPS = [
    "Gunnery",
    "Missiles",
    "Spaceship Command",
    "Navigation",
    "Engineering",
    "Shields",
    "Armor",
    "Targeting",
    "Drones",
    "Fleet Support",
]

CHARACTER_TYPES = [
    "Subcap",
    "Dreadnought",
    "Carrier",
    "FAX",
    "Supercarrier",
    "Titan",
    "Industrial",
    "Cyno Alt",
]

USER_SYLLABLES = ["ra", "zok", "ven", "kar", "mi", "thal", "dro", "sun", "bel", "qui", "nor", "ash"]
CHAR_SUFFIXES = ["", " II", " Prime", "'s Hammer", "'s Anvil", " Reborn", " Minor", " the Bold"]

N_USERS = 50
SKILLS_PER_GROUP = 8


def _name(rng: random.Random, n_syllables: int) -> str:
    return "".join(rng.choice(USER_SYLLABLES) for _ in range(n_syllables)).capitalize()


def generate() -> tuple[dict, dict]:
    rng = random.Random(SEED)

    # --- skill catalogue: 10 groups x 8 skills, prereq chains within a group ---
    skills = []
    for gi, group_name in enumerate(GROUPS):
        group_id = 100 + gi
        group_skill_ids: list[int] = []
        for si in range(SKILLS_PER_GROUP):
            skill_id = 1000 + gi * 20 + si
            prereqs = []
            # Later skills in a group tend to require earlier ones.
            if group_skill_ids and si >= 2:
                n_prereqs = min(rng.randint(1, 2), len(group_skill_ids))
                for pid in rng.sample(group_skill_ids, k=n_prereqs):
                    prereqs.append({"skill_id": pid, "level": rng.randint(1, 5)})
            tiers = ["Operation", "Systems", "Calibration", "Doctrine",
                     "Mastery", "Theory", "Specialist", "Command"]
            skills.append(
                {
                    "skill_id": skill_id,
                    "name": f"{group_name} {tiers[si]}",
                    "group_id": group_id,
                    "group_name": group_name,
                    "prerequisites": prereqs,
                }
            )
            group_skill_ids.append(skill_id)

    all_skill_ids = [s["skill_id"] for s in skills]

    # --- users + characters ---
    users_users = []
    skills_users = []
    next_char_id = 90_000_001
    used_names: set[str] = set()
    for user_id in range(1, N_USERS + 1):
        user_name = _name(rng, rng.randint(2, 3))
        while user_name in used_names:
            user_name = _name(rng, rng.randint(2, 3))
        used_names.add(user_name)

        n_chars = rng.choices([1, 2, 3, 4, 5], weights=[30, 30, 20, 15, 5])[0]
        chars = []
        skills_chars = []
        for ci in range(n_chars):
            char_id = next_char_id
            next_char_id += 1
            char_name = user_name + (CHAR_SUFFIXES[ci] if ci else "")
            # Mains are usually subcap pilots; alts skew capital/utility.
            if ci == 0:
                char_type = rng.choices(CHARACTER_TYPES, weights=[50, 10, 10, 5, 5, 3, 10, 7])[0]
            else:
                char_type = rng.choices(CHARACTER_TYPES, weights=[15, 20, 15, 10, 5, 5, 10, 20])[0]
            chars.append(
                {"character_id": char_id, "name": char_name, "character_type": char_type}
            )
            n_skills = rng.randint(15, 60)
            trained = rng.sample(all_skill_ids, k=n_skills)
            skills_chars.append(
                {
                    "character_id": char_id,
                    "skills": [
                        {
                            "skill_id": sid,
                            "level": rng.choices([1, 2, 3, 4, 5], weights=[10, 15, 25, 30, 20])[0],
                        }
                        for sid in sorted(trained)
                    ],
                }
            )
        users_users.append(
            {
                "user_id": user_id,
                "user_name": user_name,
                "main_character_id": chars[0]["character_id"],
                "characters": chars,
            }
        )
        skills_users.append({"user_id": user_id, "characters": skills_chars})

    skills_payload = {"generated_at": GENERATED_AT, "skills": skills, "users": skills_users}
    users_payload = {
        "generated_at": GENERATED_AT,
        "character_types": CHARACTER_TYPES,
        "users": users_users,
    }
    return skills_payload, users_payload


def main() -> None:
    skills_payload, users_payload = generate()
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "skills_api.json").write_text(json.dumps(skills_payload, indent=1) + "\n")
    (OUT_DIR / "users_api.json").write_text(json.dumps(users_payload, indent=1) + "\n")
    n_chars = sum(len(u["characters"]) for u in users_payload["users"])
    print(f"wrote {len(skills_payload['skills'])} skills, {N_USERS} users, {n_chars} characters")


if __name__ == "__main__":
    main()
