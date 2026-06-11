# NV Tools — Users API

Returns NV members with characters, Discord ID, rank, teams, and allowed apps.

## Request

GET https://tools.novacancies.space/api/users
Authorization: Bearer <your-token>

Optional query param:
- user_name — return only this user (case-insensitive). Omit for all users.

## Response

200 OK — JSON array:

[
  {
    "user_name": "SomeUser",
    "main_character_id": 123456789,
    "characters": [
      { "character_id": 123456789, "character_name": "Main Char" },
      { "character_id": 987654321, "character_name": "Alt Char" }
    ],
    "discord_id": "112233445566778899",
    "rank": "Member",
    "teams": ["logistics", "fc"],
    "allowed_apps": ["moon_appraiser", "asset_search"]
  }
]

- discord_id is null if Discord isn't linked.
- teams / allowed_apps are always arrays (may be empty).

## Example

curl -H "Authorization: Bearer <your-token>" \
  "https://tools.novacancies.space/api/users?user_name=SomeUser"