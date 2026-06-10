"""Generate deterministic demo fixtures conforming to docs/upstream-api.md.

Users and characters are fake, but their trained skills are sampled from the
REAL SDE catalogue so DATA_SOURCE=demo behaves like production: run
`python scripts/refresh_sde.py` first to populate var/sde/skills.json, then

    uv run python scripts/gen_demo_fixtures.py

and commit the output. data_demo/sde_skills.json is a real-skill subset
(sampled skills + their prerequisite closure) used as the offline fallback
catalogue when no var/sde artifact exists; with the full artifact present the
picker shows every SDE skill and the demo matches still work because the
trained ids are real.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data_demo"
SDE_ARTIFACT = ROOT / "var" / "sde" / "skills.json"
GENERATED_AT = "2026-01-01T00:00:00Z"
SEED = 1337

# Pool groups: which of a user's characters a query considers.
CHARACTER_GROUPS = ["Home", "Strat", "Farm", "Alpha"]

USER_SYLLABLES = ["ra", "zok", "ven", "kar", "mi", "thal", "dro", "sun", "bel", "qui", "nor", "ash"]
CHAR_SUFFIXES = ["", " II", " Prime", "'s Hammer", "'s Anvil", " Reborn", " Minor", " the Bold"]

N_USERS = 50
N_SAMPLED_SKILLS = 70  # random picks beyond the preferred list, before prereq closure

# Well-known skills people will actually search for — always in the demo
# trained pool so test queries against them return matches. Matched by exact
# name against the real artifact; missing names are skipped with a warning.
PREFERRED_SKILLS = [
    "Caldari Frigate", "Gallente Frigate", "Amarr Frigate", "Minmatar Frigate",
    "Caldari Cruiser", "Gallente Cruiser", "Amarr Cruiser", "Minmatar Cruiser",
    "Caldari Battleship", "Gallente Battleship", "Amarr Battleship", "Minmatar Battleship",
    "Caldari Dreadnought", "Gallente Dreadnought", "Amarr Dreadnought", "Minmatar Dreadnought",
    "Caldari Carrier", "Gallente Carrier", "Amarr Carrier", "Minmatar Carrier",
    "Caldari Titan", "Gallente Titan", "Amarr Titan", "Minmatar Titan",
    "Gunnery", "Small Hybrid Turret", "Large Hybrid Turret", "Large Projectile Turret",
    "Large Energy Turret", "Capital Hybrid Turret", "Capital Projectile Turret",
    "Missile Launcher Operation", "Heavy Missiles", "Cruise Missiles", "Torpedoes",
    "Cynosural Field Theory", "Jump Drive Calibration", "Jump Drive Operation",
    "Logistics Cruisers", "Command Ships", "Interdictors", "Heavy Assault Cruisers",
    "Mining", "Mining Barge", "Drones", "Heavy Drone Operation", "Fighters",
    "Shield Operation", "Repair Systems", "Mechanics", "Navigation", "Afterburner",
]


def _name(rng: random.Random, n_syllables: int) -> str:
    return "".join(rng.choice(USER_SYLLABLES) for _ in range(n_syllables)).capitalize()


def _load_real_skills() -> list[dict]:
    if not SDE_ARTIFACT.exists():
        sys.exit(
            f"ERROR: {SDE_ARTIFACT} not found — run `python scripts/refresh_sde.py` first"
        )
    return json.loads(SDE_ARTIFACT.read_text())


def _sample_catalogue(rng: random.Random, artifact: dict) -> list[dict]:
    """Preferred well-known skills + random extras, then the prerequisite
    closure so the offline fallback catalogue resolves every prereq name it
    references."""
    by_id = {s["skill_id"]: s for s in artifact["skills"]}
    by_name = {s["name"]: s["skill_id"] for s in artifact["skills"]}
    picked: set[int] = set()
    for name in PREFERRED_SKILLS:
        if name in by_name:
            picked.add(by_name[name])
        else:
            print(f"WARNING: preferred skill not in SDE: {name}", file=sys.stderr)
    ordered_ids = sorted(by_id)  # determinism regardless of artifact order
    picked |= set(rng.sample(ordered_ids, k=min(N_SAMPLED_SKILLS, len(ordered_ids))))
    frontier = list(picked)
    while frontier:
        sid = frontier.pop()
        for p in by_id[sid]["prerequisites"]:
            if p["skill_id"] in by_id and p["skill_id"] not in picked:
                picked.add(p["skill_id"])
                frontier.append(p["skill_id"])
    return [by_id[sid] for sid in sorted(picked)]


def generate() -> tuple[dict, dict, dict]:
    rng = random.Random(SEED)

    artifact = _load_real_skills()
    skills = _sample_catalogue(rng, artifact)
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
            # Mains are usually the Home character; alts skew Strat/Farm/Alpha.
            if ci == 0:
                group = rng.choices(CHARACTER_GROUPS, weights=[70, 15, 5, 10])[0]
            else:
                group = rng.choices(CHARACTER_GROUPS, weights=[15, 35, 30, 20])[0]
            chars.append({"character_id": char_id, "name": char_name, "group": group})
            n_skills = rng.randint(15, min(60, len(all_skill_ids)))
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

    sde_payload = {"sde_build_number": artifact["sde_build_number"], "skills": skills}
    skills_payload = {"generated_at": GENERATED_AT, "users": skills_users}
    users_payload = {
        "generated_at": GENERATED_AT,
        "character_groups": CHARACTER_GROUPS,
        "users": users_users,
    }
    return sde_payload, skills_payload, users_payload


def main() -> None:
    sde_payload, skills_payload, users_payload = generate()
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "sde_skills.json").write_text(json.dumps(sde_payload, indent=1) + "\n")
    (OUT_DIR / "skills_api.json").write_text(json.dumps(skills_payload, indent=1) + "\n")
    (OUT_DIR / "users_api.json").write_text(json.dumps(users_payload, indent=1) + "\n")
    n_chars = sum(len(u["characters"]) for u in users_payload["users"])
    print(
        f"wrote {len(sde_payload['skills'])} real skills "
        f"(SDE build {sde_payload['sde_build_number']}), {N_USERS} users, {n_chars} characters"
    )


if __name__ == "__main__":
    main()
