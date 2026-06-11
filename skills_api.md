EVE Tools API — Character Clones & Skills

Auth (both endpoints):
  Header: Authorization: Bearer <token>
  Method: GET
  Encoding: JSON (gzip if Accept-Encoding: gzip)

Common query param:
  user_name (optional) — filter to one user's characters.
                         Omit to return all NV-associated characters.

──────────────────────────────────────────────
GET /api/character_clones?user_name=<optional>

Returns an array, one entry per character:
[
  {
    "character_id": 123456,
    "main_character_id": 123000,
    "clones": [
      {
        "jump_clone_id": 0,            // 0 = active clone
        "name": "<< active clone >>",
        "location_id": -1,            // -1 for active clone
        "location_type": "station",  // station | structure | undocked
        "structure_name": "Jita IV - Moon 4 - CNAP",
        "solar_system": "Jita",
        "implant_type_ids": [33516, 33517],
        "implants": {
          "full_set": "High-grade Amulet",
          "other_implants": ["Ocular Filter - Improved"]
        }
      }
    ]
  }
]

──────────────────────────────────────────────
GET /api/character_skills?user_name=<optional>

Returns an array, one entry per character.
"skills" maps skill_id (string) -> trained level (1-5):
[
  {
    "character_id": 123456,
    "main_character_id": 123000,
    "skills": { "3330": 5, "3300": 4 }
  }
]