# Upstream API contract (proposed)

nvskills consumes two upstream APIs. **Neither exists yet** — this document is
the proposed contract; review it with whoever builds the real endpoints before
treating `app/sources/real.py` as final. Until then the service runs with
`DATA_SOURCE=demo` against the committed fixtures in `data_demo/`, which
conform to this contract.

The **skill catalogue is not part of either upstream API**: skill names,
groups and prerequisites come from the EVE Online SDE, processed at container
build time by `scripts/refresh_sde.py` into `var/sde/skills.json` (see
`docs/superpowers/specs/2026-06-10-skills-only-query-sde-design.md`). The
skills API only reports what each character has trained.

Both endpoints:

- `GET`, authenticated with `Authorization: Bearer <token>` (separate tokens:
  `SKILLS_API_TOKEN`, `USERS_API_TOKEN`).
- Return the **full dataset** in one response — no pagination. At corp scale
  (hundreds of users, low thousands of characters) this is well under a few MB.
- `Content-Type: application/json`.
- All IDs are integers. `character_id` is the EVE character ID. `skill_id` is
  the EVE type ID of the skill (so it joins directly against the SDE).

## Skills API — `GET {SKILLS_API_URL}`

```json
{
  "generated_at": "2026-06-10T11:30:00Z",
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

- `users[].characters[].skills` are **trained** levels (1–5), not "active"
  levels (no implant/alpha-clone adjustments). A skill absent from a
  character's list means untrained (level 0).
- Skill ids unknown to the SDE catalogue are dropped at snapshot build with a
  `snapshot.unknown_skill` warning.

## Users API — `GET {USERS_API_URL}`

```json
{
  "generated_at": "2026-06-10T11:30:00Z",
  "character_groups": ["Home", "Strat", "Farm", "Alpha"],
  "users": [
    {
      "user_id": 42,
      "user_name": "Razok",
      "main_character_id": 90001,
      "characters": [
        { "character_id": 90001, "name": "Razok Zateki", "group": "Home" },
        { "character_id": 90002, "name": "Razok's Hammer", "group": "Strat" }
      ]
    }
  ]
}
```

- `group` classifies the character's role for the **pool filter** (queries
  only consider characters whose group is selected). It is never a query
  condition. Home/Strat/Farm/Alpha is the starting vocabulary; new groups
  appearing here work without code changes.
- `characters` includes **all** of a user's characters, the main included;
  `main_character_id` must reference one of them.
- `character_groups` is the authoritative vocabulary (and display order) for
  the pool filter UI. If omitted or empty, nvskills falls back to the
  distinct set of groups seen on characters, sorted.

## Reconciliation rules (implemented in `app/snapshot/build.py`)

When the payloads disagree, the **users API is authoritative** for which
users/characters exist, their names, groups, and mains; the **SDE catalogue
is authoritative** for which skills exist:

| Situation | Behaviour |
|---|---|
| Character in skills API but not users API | Dropped; `snapshot.orphan_character` warning logged |
| User in skills API but not users API | Dropped; `snapshot.orphan_user` warning logged |
| Character in users API with no skills entry | Included with an empty skill set |
| Trained skill id not in the SDE catalogue | Dropped; `snapshot.unknown_skill` warning logged once per id |
| `main_character_id` not among the user's `characters` | Warning logged; first listed character treated as main |
| User with zero characters | Dropped; warning logged |

## Open questions for the real API

- Int vs string IDs (this doc assumes int).
- Confirm "trained" (not "active") skill levels.
- Confirm full-dataset, no-pagination responses are acceptable.
- Could both payloads be served by one endpoint? nvskills fetches both
  concurrently and joins them, so two endpoints are fine but not required.
- Confirm the `group` vocabulary and who maintains it (Home/Strat/Farm/Alpha
  proposed).
