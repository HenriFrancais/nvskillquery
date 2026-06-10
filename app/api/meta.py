"""Identity endpoint. Bearer-authenticated but NOT role-gated: the frontend
calls it first to learn whether the user passes the skill-query gate, so it
can render a friendly no-access screen instead of surfacing raw 403s."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.auth import is_skills_user

router = APIRouter()


class MeResponse(BaseModel):
    user_name: str
    user_rank: str
    user_teams: list[str]
    can_query: bool


@router.get("/api/me")
async def me(request: Request) -> MeResponse:
    return MeResponse(
        user_name=getattr(request.state, "user_name", ""),
        user_rank=getattr(request.state, "user_rank", ""),
        user_teams=list(getattr(request.state, "user_teams", [])),
        can_query=is_skills_user(request),
    )
