# Upstream API contract (proposed)

nvskills consumes two upstream APIs. **Neither exists yet** — this document is
the proposed contract; review it with whoever builds the real endpoints before
treating `app/sources/real.py` as final. Until then the service runs with
`DATA_SOURCE=demo` against the committed fixtures in `data_demo/`, which
conform to this contract.

Both endpoints:

- `GET`, authenticated with `Authorization: Bearer <token>` (separate tokens:
  `SKILLS_API_TOKEN`, `USERS_API_TOKEN`).
- Return the **full dataset** in one response — no pagination. At corp scale
  (hundreds of users, low thousands of characters) this is well under a few MB.
- `Content-Type: application/json`.
- All IDs are integers. `character_id` is the EVE character ID.

## Skills API — `GET {SKILLS_API_URL}`

```json
{
  "generated_at": "2026-06-10T11:30:00Z",
  "skills": [
    {
      "skill_id": 3300,
      "name": "Capital Hybrid Turret",
      "group_id": 255,
      "group_name": "Gunnery",
      "prerequisites": [
        { "skill_id": 3301, "level": 5 },
        { "skill_id": 3302, "level": 3 }
      ]
    }
  ],
  "users": [
    {
      "user_id": 42,
      "characters": [
        {
          "character_id": 90001,
          "skills": [
            { "skill_id": 3300, "level": 5 },
            { "skill_id": 3301, "level": 4 }
          ]
        }
      ]
    }
  ]
}
```

- `skills` is the full skill catalogue: definitions, group membership, and
  prerequisite chains. Prerequisites are **informational only** — nvskills
  displays them in the skill picker but never expands them in queries.
- `users[].characters[].skills` are **trained** levels (1–5), not "active"
  levels (no implant/alpha-clone adjustments). A skill absent from a
  character's list means untrained (level 0).

## Users API — `GET {USERS_API_URL}`

```json
{
  "generated_at": "2026-06-10T11:30:00Z",
  "character_types": ["Subcap", "Dreadnought", "Carrier", "FAX", "Supercarrier", "Titan", "Industrial", "Cyno Alt"],
  "users": [
    {
      "user_id": 42,
      "user_name": "Razok",
      "main_character_id": 90001,
      "characters": [
        { "character_id": 90001, "name": "Razok Zateki", "character_type": "Subcap" },
        { "character_id": 90002, "name": "Razok's Hammer", "character_type": "Dreadnought" }
      ]
    }
  ]
}
```

- `characters` includes **all** of a user's characters, the main included;
  `main_character_id` must reference one of them.
- `character_types` is the authoritative vocabulary for the query UI's type
  picker. If omitted or empty, nvskills falls back to the distinct set of
  types seen on characters.

## Reconciliation rules (implemented in `app/snapshot/build.py`)

When the two payloads disagree, the **users API is authoritative** for which
users/characters exist, their names, types, and mains:

| Situation | Behaviour |
|---|---|
| Character in skills API but not users API | Dropped; `snapshot.orphan_character` warning logged |
| User in skills API but not users API | Dropped; `snapshot.orphan_user` warning logged |
| Character in users API with no skills entry | Included with an empty skill set |
| `main_character_id` not among the user's `characters` | Warning logged; first listed character treated as main |
| User with zero characters | Dropped; warning logged |

## Open questions for the real API

- Int vs string IDs (this doc assumes int).
- Confirm "trained" (not "active") skill levels.
- Confirm full-dataset, no-pagination responses are acceptable.
- Could both payloads be served by one endpoint? nvskills fetches both
  concurrently and joins them, so two endpoints are fine but not required.
