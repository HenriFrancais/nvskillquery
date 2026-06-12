"""Fixture-backed data source (DATA_SOURCE=demo).

Reads the committed data_demo/*.json files so the whole service runs
end-to-end before the real upstream APIs exist.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.sources.payloads import DoctrinesApiPayload, SkillsApiPayload, UsersApiPayload


class DemoSource:
    name = "demo"

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    async def fetch_skills(self) -> SkillsApiPayload:
        raw = await asyncio.to_thread((self._data_dir / "skills_api.json").read_text)
        return SkillsApiPayload.model_validate(json.loads(raw))

    async def fetch_users(self) -> UsersApiPayload:
        raw = await asyncio.to_thread((self._data_dir / "users_api.json").read_text)
        return UsersApiPayload.model_validate(json.loads(raw))

    async def fetch_doctrines(self) -> DoctrinesApiPayload:
        path = self._data_dir / "doctrine_definitions_api.json"
        # The fixture is committed, but tolerate its absence so the rest of the
        # demo stack still boots if it hasn't been regenerated.
        if not path.exists():
            return DoctrinesApiPayload.model_validate([])
        raw = await asyncio.to_thread(path.read_text)
        return DoctrinesApiPayload.model_validate(json.loads(raw))
