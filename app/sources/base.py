"""DataSource protocol: where the two upstream payloads come from."""

from __future__ import annotations

from typing import Protocol

from app.sources.payloads import SkillsApiPayload, UsersApiPayload


class DataSource(Protocol):
    name: str

    async def fetch_skills(self) -> SkillsApiPayload: ...

    async def fetch_users(self) -> UsersApiPayload: ...
