"""Real upstream API client (DATA_SOURCE=real).

The endpoints don't exist yet — this implements the proposed contract in
docs/upstream-api.md and must be revisited once the real APIs are built.
"""

from __future__ import annotations

import httpx

from app.config import Settings
from app.sources.payloads import SkillsApiPayload, UsersApiPayload


class RealApiSource:
    name = "real"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def _get_json(self, url: str, token: str) -> object:
        if not url:
            raise RuntimeError("upstream API url not configured")
        headers = {"authorization": f"Bearer {token}"} if token else {}
        async with httpx.AsyncClient(timeout=self._settings.upstream_timeout_s) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def fetch_skills(self) -> SkillsApiPayload:
        data = await self._get_json(
            self._settings.skills_api_url, self._settings.skills_api_token
        )
        return SkillsApiPayload.model_validate(data)

    async def fetch_users(self) -> UsersApiPayload:
        data = await self._get_json(
            self._settings.users_api_url, self._settings.users_api_token
        )
        return UsersApiPayload.model_validate(data)
