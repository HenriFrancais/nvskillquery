"""Pydantic models for the two upstream API payloads.

The shapes are the proposed contract in docs/upstream-api.md; the committed
demo fixtures conform to them.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SkillPrereq(BaseModel):
    skill_id: int
    level: int = Field(ge=1, le=5)


class SkillDefIn(BaseModel):
    skill_id: int
    name: str
    group_id: int
    group_name: str
    prerequisites: list[SkillPrereq] = Field(default_factory=list)


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
    skills: list[SkillDefIn]
    users: list[SkillsUserIn]


class UsersCharacterIn(BaseModel):
    character_id: int
    name: str
    character_type: str


class UsersUserIn(BaseModel):
    user_id: int
    user_name: str
    main_character_id: int
    characters: list[UsersCharacterIn]


class UsersApiPayload(BaseModel):
    generated_at: datetime
    character_types: list[str] = Field(default_factory=list)
    users: list[UsersUserIn]
