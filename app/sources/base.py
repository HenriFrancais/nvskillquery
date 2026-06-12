"""DataSource protocol: where the two upstream payloads come from."""

from __future__ import annotations

from typing import Protocol

from app.sources.payloads import DoctrinesApiPayload, SkillsApiPayload, UsersApiPayload


class DataSource(Protocol):
    name: str

    async def fetch_skills(self) -> SkillsApiPayload: ...

    async def fetch_users(self) -> UsersApiPayload: ...

    async def fetch_doctrines(self) -> DoctrinesApiPayload: ...
