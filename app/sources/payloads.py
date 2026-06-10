"""Pydantic models for the two upstream API payloads.

The shapes are the proposed contract in docs/upstream-api.md; the committed
demo fixtures conform to them. The skill catalogue is NOT part of either
payload — it comes from the processed SDE artifact (app/sde/catalog.py);
the skills API only carries trained levels.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SkillPrereq(BaseModel):
    """Prerequisite entry in the SDE-derived skill catalogue."""

    skill_id: int
    level: int = Field(ge=1, le=5)


class TrainedSkillIn(BaseModel):
    skill_id: int
    level: int = Field(ge=1, le=5)


class SkillsCharacterIn(BaseModel):
    character_id: int
    skills: list[TrainedSkillIn] = Field(default_factory=list)


class SkillsUserIn(BaseModel):
    user_id: int
    characters: list[SkillsCharacterIn] = Field(default_factory=list)


class SkillsApiPayload(BaseModel):
    generated_at: datetime
    users: list[SkillsUserIn]


class UsersCharacterIn(BaseModel):
    character_id: int
    name: str
    group: str


class UsersUserIn(BaseModel):
    user_id: int
    user_name: str
    main_character_id: int
    characters: list[UsersCharacterIn]


class UsersApiPayload(BaseModel):
    generated_at: datetime
    character_groups: list[str] = Field(default_factory=list)
    users: list[UsersUserIn]
