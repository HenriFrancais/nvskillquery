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
