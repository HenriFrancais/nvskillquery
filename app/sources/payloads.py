"""Pydantic models for the two upstream API payloads.

The shapes are the real NV Tools contract in docs/upstream-api.md; the committed
demo fixtures conform to them. The skill catalogue is NOT part of either
payload — it comes from the processed SDE artifact (app/sde/catalog.py);
the skills API only carries trained levels.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, RootModel


class SkillPrereq(BaseModel):
    """Prerequisite entry in the SDE-derived skill catalogue."""

    skill_id: int
    level: int = Field(ge=1, le=5)


class SkillsCharacterIn(BaseModel):
    character_id: int
    main_character_id: int
    # skill_id (string in JSON) -> trained level 1-5. Pydantic coerces the
    # string keys to int. Absent skill = untrained.
    skills: dict[int, int] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}


class SkillsApiPayload(RootModel[list[SkillsCharacterIn]]):
    """`GET /api/character_skills` — a flat array, one entry per character."""


class UsersCharacterIn(BaseModel):
    character_id: int
    character_name: str

    model_config = {"extra": "ignore"}


class UsersUserIn(BaseModel):
    user_name: str
    main_character_id: int
    characters: list[UsersCharacterIn] = Field(default_factory=list)
    # Carried for completeness / forward-compat; not consumed by the snapshot.
    discord_id: str | None = None
    rank: str = ""
    teams: list[str] = Field(default_factory=list)
    allowed_apps: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class UsersApiPayload(RootModel[list[UsersUserIn]]):
    """`GET /api/users` — a flat array, one entry per user."""
