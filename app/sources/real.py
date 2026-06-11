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
        # httpx advertises Accept-Encoding and decompresses gzip itself.
        headers = {"authorization": f"Bearer {token}"} if token else {}
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
