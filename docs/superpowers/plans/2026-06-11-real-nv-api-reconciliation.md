# Real NV API Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Switch nvskills from the *proposed* upstream contract to the **real** NV Tools `users` and `character_skills` APIs, and document deployment under `/skillquery` on the shared VM.

**Architecture:** The real APIs differ from `docs/upstream-api.md` in shape (flat arrays, string-keyed skill maps, `character_name`, no `user_id`, no per-character `group`) and auth (one bearer, one base host). We reshape only the **payload boundary** (`app/sources/payloads.py`, `real.py`) and the **snapshot join** (`app/snapshot/build.py`). Internally we keep `user_id: int` (sourced from each user's `main_character_id`) and the pool-filter machinery, but make the pool **inert**: every character is placed in one default group `"All"`. This leaves `app/snapshot/models.py`, the whole query pipeline, and the **entire frontend** unchanged — `api.ts` still receives `user_id: number` and `character_groups: string[]`.

**Tech Stack:** FastAPI + pydantic v2 (backend), pytest, React/Vite (frontend, untouched), Docker + Caddy (deploy).

---

## Context the engineer needs

**The real APIs** (specs in `users_api.md`, `skills_api.md` at repo root):

- `GET https://tools.novacancies.space/api/users?user_name=<optional>` → **flat JSON array**:
  ```json
  [ { "user_name": "SomeUser", "main_character_id": 123456789,
      "characters": [ { "character_id": 123456789, "character_name": "Main Char" } ],
      "discord_id": "112233445566778899", "rank": "Member",
      "teams": ["logistics"], "allowed_apps": ["moon_appraiser"] } ]
  ```
  No `user_id`, no per-character `group`, no top-level `character_groups`/`generated_at`. Character name field is `character_name` (not `name`).

- `GET https://tools.novacancies.space/api/character_skills?user_name=<optional>` → **flat JSON array**, one entry per character:
  ```json
  [ { "character_id": 123456, "main_character_id": 123000, "skills": { "3330": 5, "3300": 4 } } ]
  ```
  `skills` is a **map of skill_id (string) → trained level**, not a list. No user nesting, no `generated_at`.

- Both: `Authorization: Bearer <token>` with the **same** token (`NV_API_TOKEN`). gzip if `Accept-Encoding: gzip`. There is also a `/api/character_clones` endpoint — **not used** (this app is skills-only).

**Key modelling decisions (already made with the user):**

1. **One token, one base URL.** Collapse `SKILLS_API_*` / `USERS_API_*` → `NV_API_TOKEN` + `NV_API_URL` (base, default `https://tools.novacancies.space/api`); derive `/users` and `/character_skills` from the base.
2. **`user_id` is kept internally** but sourced from `main_character_id` (the only stable int identity in the real API). Nothing downstream changes.
3. **Pool filter kept but inert.** The real API has no character group, so `build_snapshot` assigns every character `group = "All"` and sets `character_groups = ("All",)`. The pool-filter code and its *unit* tests stay (so it's trivially re-enabled if `group` is ever added upstream); the demo/integration tests collapse to the single `"All"` group to mirror production.

**Where the bearer token goes (the user's question):** `/home/matron/dev/nvskills/.env` — already gitignored (`.gitignore` line `.env`). Add `NV_API_TOKEN=<value>`. The committed `.env.example` documents the name with no value.

**Run the suite with:** `uv run pytest -q` from the repo root.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `docs/upstream-api.md` | rewrite | Honest contract doc matching the real APIs |
| `app/sources/payloads.py` | rewrite models | Real payload shapes (RootModel lists) |
| `app/sources/real.py` | rewrite client | One base URL + token, two derived endpoints |
| `app/config.py` | edit fields | `nv_api_url` + `nv_api_token` replace 4 fields |
| `.env.example` | edit | Document `NV_API_URL` / `NV_API_TOKEN` |
| `docker-compose.yml` | edit env block | Pass `NV_API_URL` / `NV_API_TOKEN` |
| `app/snapshot/build.py` | rewrite join | Join on `character_id`; `user_id := main_character_id`; group `"All"` |
| `scripts/migrate_demo_fixtures.py` | create | One-shot, network-free transform of committed fixtures to new shapes |
| `scripts/gen_demo_fixtures.py` | edit | Emit new shapes for future regenerations |
| `data_demo/skills_api.json`, `users_api.json` | regenerate | New-shape committed fixtures |
| `tests/helpers.py` | edit | `simple_snapshot` builds directly (multi-group); `snapshot_from` new shapes |
| `tests/test_snapshot_store.py` | edit | `FakeSource` returns new shapes |
| `tests/test_aggregate.py` | edit | Build-rules tests use new shapes; group asserts → `"All"` |
| `tests/test_fixtures.py` | edit | Asserts `("All",)` |
| `tests/test_api_integration.py` | edit | Demo ground truth from new-shape fixtures; pool group `"All"`; `NV_API_URL` |
| `deploy/Caddyfile` | create | Shared VM reverse-proxy config incl. `/skillquery` |
| `README.md` | create | Local dev, env, and the remote Caddyfile entry to add |

---

### Task 1: Rewrite the upstream contract doc

**Files:**
- Modify: `docs/upstream-api.md`

- [ ] **Step 1: Replace the doc body**

Overwrite `docs/upstream-api.md` with the real contract. Use this content:

```markdown
# Upstream API contract (real)

nvskills consumes two **real** NV Tools endpoints (specs: `users_api.md`,
`skills_api.md` at the repo root). Both are `GET`, authenticated with a single
`Authorization: Bearer <NV_API_TOKEN>`, served from one base host
(`NV_API_URL`, default `https://tools.novacancies.space/api`). Each returns the
full dataset as a flat JSON array (no pagination, no envelope). gzip is
available via `Accept-Encoding: gzip`.

The **skill catalogue is not part of either API** — skill names, groups and
prerequisites come from the EVE SDE, processed at container build time by
`scripts/refresh_sde.py` into `var/sde/skills.json`. The skills API only
reports trained levels.

## Users API — `GET {NV_API_URL}/users`

    [ { "user_name": "SomeUser",
        "main_character_id": 123456789,
        "characters": [ { "character_id": 123456789, "character_name": "Main Char" } ],
        "discord_id": "112233445566778899",
        "rank": "Member",
        "teams": ["logistics"],
        "allowed_apps": ["moon_appraiser"] } ]

- Identity is `user_name` + `main_character_id` (there is **no** `user_id`).
- `characters` includes all of a user's characters, main included; the
  character name field is `character_name`.
- `discord_id` may be null; `teams` / `allowed_apps` are always arrays.
- There is **no per-character `group`** and no `character_groups` vocabulary.
  nvskills keeps its pool-filter machinery but places every character in a
  single default group `"All"` (the feature is inert until/unless a `group`
  field is added upstream). `rank` / `teams` / `allowed_apps` are accepted but
  not consumed (access gating uses the proxy's `X-User-*` headers, not this
  payload).

## Skills API — `GET {NV_API_URL}/character_skills`

    [ { "character_id": 123456,
        "main_character_id": 123000,
        "skills": { "3330": 5, "3300": 4 } } ]

- One entry per character. `skills` maps skill_id (string) → **trained** level
  (1–5). A skill absent from the map means untrained (level 0).
- Joined to users on `character_id`. Skill ids unknown to the SDE catalogue are
  dropped at snapshot build with a `snapshot.unknown_skill` warning.

## Reconciliation rules (implemented in `app/snapshot/build.py`)

The users API is authoritative for which users/characters exist, their names
and mains; the SDE catalogue is authoritative for which skills exist.

| Situation | Behaviour |
|---|---|
| Skills entry whose `character_id` is not in the users API | Dropped; `snapshot.orphan_character` warning |
| Character in users API with no skills entry | Included with an empty skill set |
| Trained skill id not in the SDE catalogue | Dropped; `snapshot.unknown_skill` warning (once per id) |
| `main_character_id` not among the user's `characters` | Warning; first listed character treated as main |
| User with zero characters | Dropped; warning |

Internally, each user's stable int identity (`user_id` in the snapshot models
and API responses) is its `main_character_id`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/upstream-api.md
git commit -m "docs: reconcile upstream-api contract with the real NV APIs"
```

---

### Task 2: Refactor `simple_snapshot` to build directly (no behaviour change)

This isolates the pool-filter unit tests from the upcoming payload reshape: they need multiple groups, which the new group-less payload can no longer express. We build those snapshots directly from records instead of through `build_snapshot`. Done first so the suite stays green at each later step.

**Files:**
- Modify: `tests/helpers.py`
- Test: `tests/test_aggregate.py` (run only — unchanged)

- [ ] **Step 1: Replace `simple_snapshot` with a direct builder**

In `tests/helpers.py`, replace the entire `simple_snapshot` function (currently lines ~77–119) with a version that constructs the `Snapshot` directly. Keep the exact same ground truth (ids, names, groups, skills) so `test_aggregate.py` passes unchanged. Add the needed imports (`Snapshot`, `UserRecord` are already imported; ensure `UserRecord` is in the import from `app.snapshot.models`).

```python
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
```

- [ ] **Step 2: Run the suite to confirm no regression**

Run: `uv run pytest -q`
Expected: PASS (this refactor preserves the old ground truth; `build_snapshot` and payloads are still the old shape at this point).

- [ ] **Step 3: Commit**

```bash
git add tests/helpers.py
git commit -m "test: build simple_snapshot directly to decouple pool tests from payload shape"
```

---

### Task 3: Reshape payload models, the real client, and config

This is the core data-boundary change. The suite will be **red** between steps and green again at the end of Task 5; that's expected — these files form one atomic reshape. Commit at the end of Task 5.

**Files:**
- Modify: `app/sources/payloads.py`
- Modify: `app/sources/real.py`
- Modify: `app/config.py`
- Modify: `.env.example`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Rewrite the upstream payload models**

Replace the upstream-payload section of `app/sources/payloads.py` (everything from `class TrainedSkillIn` to the end of the file — keep `SkillPrereq`, which the SDE catalogue uses) with:

```python
from pydantic import RootModel


class SkillsCharacterIn(BaseModel):
    character_id: int
    main_character_id: int
    # skill_id (string in JSON) -> trained level 1-5. Pydantic coerces the
    # string keys to int. Absent skill = untrained.
    skills: dict[int, int] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}


class SkillsApiPayload(RootModel[list[SkillsCharacterIn]]):
    """`GET /api/character_skills` — a flat array, one entry per character."""


class UsersCharacterIn(BaseModel):
    character_id: int
    character_name: str

    model_config = {"extra": "ignore"}


class UsersUserIn(BaseModel):
    user_name: str
    main_character_id: int
    characters: list[UsersCharacterIn] = Field(default_factory=list)
    # Carried for completeness / forward-compat; not consumed by the snapshot.
    discord_id: str | None = None
    rank: str = ""
    teams: list[str] = Field(default_factory=list)
    allowed_apps: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class UsersApiPayload(RootModel[list[UsersUserIn]]):
    """`GET /api/users` — a flat array, one entry per user."""
```

Remove the now-unused `from datetime import datetime` import. Keep the `SkillPrereq` class and the `from pydantic import BaseModel, Field` import (add `RootModel`).

- [ ] **Step 2: Replace the env fields in `app/config.py`**

In `app/config.py`, replace the four upstream-API fields (lines ~43–46):

```python
    skills_api_url: str = ""
    skills_api_token: str = ""
    users_api_url: str = ""
    users_api_token: str = ""
```

with:

```python
    # Real NV Tools APIs share one base host + one bearer token. Endpoints
    # (/users, /character_skills) are derived from the base in real.py.
    nv_api_url: str = "https://tools.novacancies.space/api"
    nv_api_token: str = ""
```

- [ ] **Step 3: Rewrite the real client**

Replace the body of `app/sources/real.py` with:

```python
"""Real upstream API client (DATA_SOURCE=real).

Talks to the NV Tools `users` and `character_skills` endpoints — one base
host, one bearer token (see docs/upstream-api.md).
"""

from __future__ import annotations

import httpx

from app.config import Settings
from app.sources.payloads import SkillsApiPayload, UsersApiPayload


class RealApiSource:
    name = "real"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _endpoint(self, path: str) -> str:
        base = self._settings.nv_api_url.rstrip("/")
        if not base:
            raise RuntimeError("NV_API_URL not configured")
        return f"{base}/{path}"

    async def _get_json(self, path: str) -> object:
        url = self._endpoint(path)
        token = self._settings.nv_api_token
        headers = {"accept-encoding": "gzip"}
        if token:
            headers["authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=self._settings.upstream_timeout_s) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def fetch_skills(self) -> SkillsApiPayload:
        data = await self._get_json("character_skills")
        return SkillsApiPayload.model_validate(data)

    async def fetch_users(self) -> UsersApiPayload:
        data = await self._get_json("users")
        return UsersApiPayload.model_validate(data)
```

- [ ] **Step 4: Update `.env.example`**

Replace the upstream-API block (lines ~14–18) in `.env.example`:

```bash
# Upstream APIs (see docs/upstream-api.md for the expected payloads).
SKILLS_API_URL=
SKILLS_API_TOKEN=
USERS_API_URL=
USERS_API_TOKEN=
```

with:

```bash
# Real NV Tools API (see docs/upstream-api.md). One base host serves both
# /users and /character_skills; one bearer token authenticates both. Get the
# token from the NV Tools admin; put it in .env (this file's gitignored
# sibling), never here.
NV_API_URL=https://tools.novacancies.space/api
NV_API_TOKEN=
```

- [ ] **Step 5: Update `docker-compose.yml`**

Replace the four `SKILLS_/USERS_` env lines (lines ~19–22) with:

```yaml
      NV_API_URL: ${NV_API_URL:-https://tools.novacancies.space/api}
      NV_API_TOKEN: ${NV_API_TOKEN:-}
```

(Do not commit yet — the suite is red until Task 5.)

---

### Task 4: Rewrite the snapshot join

**Files:**
- Modify: `app/snapshot/build.py`

- [ ] **Step 1: Replace `build_snapshot`**

Replace the body of `app/snapshot/build.py` (keep the imports; they're unchanged) with:

```python
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
```

Update the module docstring's reference to "user_id" if desired (optional). (Still red — fixtures/tests next.)

---

### Task 5: Regenerate demo fixtures and fix the payload-shaped tests

**Files:**
- Create: `scripts/migrate_demo_fixtures.py`
- Modify: `data_demo/skills_api.json`, `data_demo/users_api.json` (via the script)
- Modify: `scripts/gen_demo_fixtures.py`
- Modify: `tests/helpers.py`, `tests/test_snapshot_store.py`, `tests/test_aggregate.py`, `tests/test_fixtures.py`, `tests/test_api_integration.py`

- [ ] **Step 1: Write a network-free fixture migration script**

Create `scripts/migrate_demo_fixtures.py`. It transforms the committed old-shape fixtures into the real shapes in place (no SDE download, deterministic, preserves all real skill ids and the 50-user / 100+-character counts the tests assert):

```python
"""One-shot: rewrite data_demo/{skills,users}_api.json from the old proposed
contract into the real NV API shapes. Network-free and deterministic — reads
the committed fixtures and rewrites them. Safe to re-run (idempotent on
already-migrated files would fail validation, so run once on the old files).

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
            "main_character_id": main_of.get(c["character_id"], c["character_id"]),
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
```

- [ ] **Step 2: Run the migration**

Run: `uv run python scripts/migrate_demo_fixtures.py`
Expected: prints `migrated 50 users, <N> character skill entries` and rewrites both files in place.

- [ ] **Step 3: Patch `scripts/gen_demo_fixtures.py` for future regenerations**

So a future regenerate produces the real shapes (not the old contract). Make these edits in `scripts/gen_demo_fixtures.py`:

Find where the skills payload is assembled (around line 150):

```python
    skills_payload = {"generated_at": GENERATED_AT, "users": skills_users}
```

The generator currently builds `skills_users` as `[{user_id, characters:[{character_id, skills:[{skill_id, level}]}]}]` and the users payload as the old object. Replace the final assembly + write with new-shape construction. Locate the block that builds `skills_users` / `users_payload` and the two `json.dump`s, and replace the payload assembly so it emits:

```python
    # Real-shape skills API: flat list, one entry per character, skills as a map.
    main_of = {
        c["character_id"]: u["main_character_id"]
        for u in users_payload["users"]
        for c in u["characters"]
    }
    skills_payload = [
        {
            "character_id": c["character_id"],
            "main_character_id": main_of[c["character_id"]],
            "skills": {str(s["skill_id"]): s["level"] for s in c["skills"]},
        }
        for u in skills_users
        for c in u["characters"]
    ]
    # Real-shape users API: flat list, character_name, no group/user_id.
    users_payload = [
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
        for u in users_payload["users"]
    ]
```

Adjust to the generator's actual variable names (it builds `users_payload` as a dict with `"users"`; reference `users_payload["users"]` before reassigning). Remove the now-unused `CHARACTER_GROUPS` per-character assignment only if it becomes dead; leaving it is harmless. The generator is not run by tests/CI, so correctness here is verified by re-running it manually only if needed — the committed fixtures come from Step 2.

- [ ] **Step 4: Update `tests/helpers.py` `snapshot_from`**

Replace `snapshot_from` (lines ~51–66) so it accepts new-shape **lists** and drops `generated_at`:

```python
def snapshot_from(
    catalog_skills: list[dict],
    skills_entries: list[dict],
    users_entries: list[dict],
    version: int = 1,
    fetched_at: float = 0.0,
) -> Snapshot:
    """Build a snapshot from raw real-shape payload lists (validated through
    the upstream models, same as production) plus an SDE catalogue."""
    return build_snapshot(
        SkillsApiPayload.model_validate(skills_entries),
        UsersApiPayload.model_validate(users_entries),
        catalog=catalog_from(catalog_skills),
        version=version,
        fetched_at=fetched_at,
    )
```

Delete the now-unused `GENERATED_AT` constant (line ~10) if nothing else in the file uses it.

- [ ] **Step 5: Update `tests/test_snapshot_store.py` `FakeSource`**

Replace the two `fetch_*` methods (lines ~33–57) and drop `GENERATED_AT`:

```python
    async def fetch_skills(self) -> SkillsApiPayload:
        self.fetches += 1
        if self.fail:
            raise RuntimeError("upstream down")
        return SkillsApiPayload.model_validate([])

    async def fetch_users(self) -> UsersApiPayload:
        return UsersApiPayload.model_validate(
            [
                {
                    "user_name": "Alice",
                    "main_character_id": 101,
                    "characters": [
                        {"character_id": 101, "character_name": "Alice"}
                    ],
                }
            ]
        )
```

Remove the `GENERATED_AT = ...` line (~15).

- [ ] **Step 6: Update the build-rules tests in `tests/test_aggregate.py`**

Replace `test_build_drops_orphans_and_fixes_bad_main` (lines ~133–160) with:

```python
def test_build_drops_orphans_and_fixes_bad_main():
    snap = snapshot_from(
        CATALOG_SKILLS,
        # skills API: flat list per character
        [
            {"character_id": 999, "main_character_id": 701, "skills": {}},  # orphan
            {"character_id": 701, "main_character_id": 701, "skills": {}},
        ],
        # users API: flat list
        [
            # main_character_id points at a character not in the list → falls
            # back to the first character (701), which becomes the user key.
            {"user_name": "Dave", "main_character_id": 12345, "characters": [
                {"character_id": 701, "character_name": "Dave"},
            ]},
            # zero characters → dropped entirely
            {"user_name": "Eve", "main_character_id": 1, "characters": []},
        ],
    )
    assert set(snap.users) == {701}
    assert snap.users[701].main_character_id == 701
    assert snap.characters[701].is_main
    # Pool is inert: a single default group.
    assert snap.character_groups == ("All",)
    assert snap.characters[701].group == "All"
```

Replace `test_build_drops_unknown_trained_skills` (lines ~163–185) with:

```python
def test_build_drops_unknown_trained_skills():
    snap = snapshot_from(
        CATALOG_SKILLS,
        [{"character_id": 101, "main_character_id": 101,
          "skills": {"1": 5, "999": 3}}],  # 999 not in SDE catalogue
        [{"user_name": "Alice", "main_character_id": 101, "characters": [
            {"character_id": 101, "character_name": "Alice"}]}],
    )
    assert snap.characters[101].skill_levels == {1: 5}
```

(The pool-filter tests above this section, all using `simple_snapshot()`, are unchanged — they keep their multi-group ground truth from Task 2.)

- [ ] **Step 7: Update `tests/test_fixtures.py`**

Change the two group assertions (lines ~49 and ~63):

```python
    assert snap.character_groups == ("All",)
```
and
```python
    assert {c.group for c in snap.characters.values()} == {"All"}
```

Everything else in that test (50 users, ≥100 characters, skills reference the catalogue, mains first) holds because the migration preserved ids and counts.

- [ ] **Step 8: Update `tests/test_api_integration.py`**

a) Fix the demo-ground-truth derivation (lines ~6, ~23–28):

Change the module docstring line 6 to:
```python
50 users and a single inert "All" pool group are generator constants.
```

Change the `COMMON_SKILL_ID` computation (the skills fixture is now a flat list with a `skills` map):
```python
COMMON_SKILL_ID = Counter(
    int(sid)
    for c in DEMO_TRAINED
    for sid in c["skills"]
).most_common(1)[0][0]
```

b) Catalog assertion (line ~81):
```python
    assert cat["character_groups"] == ["All"]
```

c) Cache test (line ~218): change the pool to a valid group:
```python
    body = {**SIMPLE_QUERY, "groups": ["All"]}
```

d) CSV groups param test (line ~260): change `g=Home` to `g=All`:
```python
    home = client.get(f"/api/query/export.csv?q={q}&g=All", headers=GATED_HEADERS)
```
(The `g=Nope` unknown-group case on line ~264 stays — `"Nope"` is still not a known group.)

e) Pool-scope test (`test_query_groups_scope_pool`, ~line 146): change the group to `"All"`:
```python
        json={**SIMPLE_QUERY, "groups": ["All"]},
```
and the per-character assertion:
```python
        assert all(c["group"] == "All" for c in row["matching_characters"])
```

f) 503 test (line ~194): swap the env override to the new var name:
```python
    client = make_client(DATA_SOURCE="real", NV_API_URL="")
```

- [ ] **Step 9: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS (all tests green).

- [ ] **Step 10: Commit the whole reshape**

```bash
git add app/sources/payloads.py app/sources/real.py app/config.py \
        app/snapshot/build.py .env.example docker-compose.yml \
        scripts/migrate_demo_fixtures.py scripts/gen_demo_fixtures.py \
        data_demo/skills_api.json data_demo/users_api.json \
        tests/helpers.py tests/test_snapshot_store.py tests/test_aggregate.py \
        tests/test_fixtures.py tests/test_api_integration.py
git commit -m "feat: consume the real NV users/character_skills APIs (single token, inert pool)"
```

- [ ] **Step 11: Lint/type check (match repo conventions)**

Run: `uv run ruff check . && uv run mypy app`
Expected: clean. Fix any issues (e.g. unused imports) and amend the commit.

---

### Task 6: Deployment — README and the shared Caddyfile entry

The container already binds `127.0.0.1:8083` (`docker-compose.yml`) and satisfies the NV Tools contract (bearer 401 boundary, `X-User-*`, CSP `frame-ancestors`, `nv_embed.js`, stateless, URL-prefix aware). This task documents how it slots onto the shared VM under `/skillquery`, alongside eve-router (`/ops/bd`) and nvinfo (`/wiki`).

**Files:**
- Create: `deploy/Caddyfile`
- Create: `README.md`

- [ ] **Step 1: Create `deploy/Caddyfile`**

This is the **shared** VM reverse-proxy file — it must list all three apps so reloading it never drops a sibling. Mirror `~/dev/nvinfo/deploy/Caddyfile` and add the `/skillquery` matcher:

```caddyfile
# TLS reverse proxy for the raz-tools integration host.
#
# ⚠️  SHARED FILE — this single hostname fronts eve-router (/ops/bd), nvinfo
# (/wiki) AND nvskills (/skillquery) on the same VM. NV Tools authenticates
# each user and path-routes to this one hostname; Caddy terminates TLS on :443
# and dispatches by URL prefix to the right loopback-bound container. Do NOT
# replace this with a single catch-all `reverse_proxy` — that hijacks the whole
# hostname and 404s the other apps. Keep these matchers in sync with the
# sibling eve-router and nvinfo deploy/Caddyfile copies.
#
# Install on the VM at /etc/caddy/Caddyfile, then:
#   sudo caddy validate --config /etc/caddy/Caddyfile
#   sudo systemctl reload caddy

tools-integration-raz.novacancies.space {
	# eve-router — mounted at /ops/bd. flush_interval -1 + zeroed timeouts are
	# mandatory: it streams map_changed SSE pings Caddy would otherwise buffer.
	@router path /ops/bd /ops/bd/*
	reverse_proxy @router 127.0.0.1:8000 {
		flush_interval -1
		transport http {
			read_timeout 0
			write_timeout 0
		}
	}

	# nvinfo wiki — mounted at /wiki. No SSE.
	@wiki path /wiki /wiki/*
	reverse_proxy @wiki 127.0.0.1:8081

	# nvskills skill-query — mounted at /skillquery. No SSE; the app keeps its
	# /skillquery prefix (do NOT use handle_path, which strips it).
	@skillquery path /skillquery /skillquery/*
	reverse_proxy @skillquery 127.0.0.1:8083
}
```

- [ ] **Step 2: Create `README.md`**

```markdown
# nvskills — skill-query service

Corp skill-query tool: build a skills-only boolean query and see which NV
members (across all their characters) satisfy it. Runs as an authenticated
iframe inside NV Tools (`tools.novacancies.space`) under `/skillquery`.

## Local development

    uv sync
    uv run python scripts/refresh_sde.py        # populate var/sde/skills.json (~80 MB once)
    DEV_MODE=1 DEV_USER_RANK=CEO DATA_SOURCE=demo uv run uvicorn app.main:app --reload

`DATA_SOURCE=demo` serves the committed fixtures in `data_demo/`; the SDE step
is optional in demo mode (it falls back to `data_demo/sde_skills.json`). Run
the tests with `uv run pytest -q`.

## Configuration

Secrets and per-deployment values come from `.env` (gitignored; copy
`.env.example`). The access-gate allowlist (which ranks/teams may query) is in
`config.toml` / `config.local.toml`.

| Var | Purpose |
|---|---|
| `NV_TOKEN` | Shared bearer the NV Tools proxy sends; the app 401s without it. |
| `NV_API_URL` | Base host for the real APIs (default `https://tools.novacancies.space/api`). |
| `NV_API_TOKEN` | **Bearer for the upstream users/character_skills APIs. Put it in `.env` only.** Obtain from the NV Tools admin. |
| `URL_PREFIX` | Path the app mounts under; `/skillquery` in production, empty for local root. |
| `DATA_SOURCE` | `real` (hits the NV APIs) or `demo` (committed fixtures). |

The upstream API contract is documented in `docs/upstream-api.md`.

## Deployment (shared VM behind NV Tools)

Topology: NV Tools authenticates the user and forwards over HTTPS to this VM;
Caddy terminates TLS on `:443` and reverse-proxies to the loopback-bound
container. The container binds `127.0.0.1:8083` only. See the
`nv-tools-service-deploy` skill / `~/dev/router/nvtools.txt` for the full
contract.

1. **Build and run the container** (on the VM):

       cd ~/dev/nvskills
       echo "NV_TOKEN=<shared-proxy-secret>"  >> .env
       echo "NV_API_TOKEN=<upstream-api-token>" >> .env
       echo "URL_PREFIX=/skillquery"           >> .env
       echo "DATA_SOURCE=real"                  >> .env
       docker compose build && docker compose up -d

   `URL_PREFIX=/skillquery` is passed as both the runtime env var and the
   `VITE_URL_PREFIX` build arg (wired in `docker-compose.yml`) so the SPA and
   the backend agree on the prefix.

2. **Add the Caddy entry on the remote.** This VM already fronts eve-router and
   nvinfo from a single shared `/etc/caddy/Caddyfile`. Edit that file (do **not**
   overwrite it) and add the nvskills matcher **inside** the existing
   `tools-integration-raz.novacancies.space { … }` block:

       # nvskills skill-query — mounted at /skillquery. No SSE; keep the prefix.
       @skillquery path /skillquery /skillquery/*
       reverse_proxy @skillquery 127.0.0.1:8083

   The canonical full file (all three apps) is committed at `deploy/Caddyfile`.
   Do **not** use `handle_path` — the app serves its routes under `/skillquery`
   and a stripped prefix 404s. Then validate and reload:

       sudo caddy validate --config /etc/caddy/Caddyfile
       sudo systemctl reload caddy

3. **Tell the NV Tools admin** the public path is `/skillquery` and confirm the
   exact path their proxy forwards to your upstream (it must equal
   `URL_PREFIX`). Give them the VM's public IP + hostname; they set DNS and
   point NV Tools at your `https://` upstream, and hand you the `NV_TOKEN`
   bearer (must match `.env` exactly).

### Verify

    # 401 = bearer boundary works (loopback, no auth)
    curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8083/skillquery/
    # 401 over TLS = Caddy reaches the app
    curl -is https://tools-integration-raz.novacancies.space/skillquery/ | head -1
    # 200 + CSP = authed request works
    curl -is -H "Authorization: Bearer <NV_TOKEN>" -H "X-User-Name: You" \
         -H "X-User-Rank: CEO" \
         https://tools-integration-raz.novacancies.space/skillquery/ \
      | grep -iE "HTTP/|content-security-policy"
```

- [ ] **Step 3: Commit**

```bash
git add deploy/Caddyfile README.md
git commit -m "docs: deployment README + shared Caddyfile entry for /skillquery"
```

---

## Self-Review notes

- **Spec coverage:** single token (`NV_API_TOKEN`) in `.env` ✅ (Task 3 + README); APIs reconciled against the plan ✅ (Tasks 1, 3, 4); deploy like router/nvinfo under `/skillquery` ✅ (Task 6, port 8083, prefix passthrough); Caddyfile entry in README ✅ (Task 6 Step 2).
- **Inert pool decision:** group forced to `"All"` in `build.py`; pool *logic* still unit-tested via direct-built `simple_snapshot` (Task 2); demo/integration tests collapsed to `"All"`.
- **No frontend changes:** `api.ts` contract (`user_id: number`, `character_groups: string[]`) is preserved because `user_id := main_character_id` and `character_groups = ("All",)`.
- **Type consistency:** `SkillsApiPayload`/`UsersApiPayload` are `RootModel` lists; `build_snapshot` reads `.root`; `snapshot_from` passes lists; `CharacterRecord`/`UserRecord` field names unchanged.

## Out of scope

- `/api/character_clones` (clones/implants) — this app is skills-only.
- Consuming `rank`/`teams`/`allowed_apps` from the users API for gating (gate still uses `X-User-*` headers). `allowed_apps` could later restrict access to users with `"skillquery"` — not now.
- VM provisioning, DNS, and the NV Tools admin handshake (operational, covered by README + the deploy skill).
```
