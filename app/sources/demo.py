"""Fixture-backed data source (DATA_SOURCE=demo).

Reads the committed data_demo/*.json files so the whole service runs
end-to-end before the real upstream APIs exist.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.sources.payloads import SkillsApiPayload, UsersApiPayload


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
