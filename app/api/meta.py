"""Identity endpoint. Bearer-authenticated but NOT access-gated: the frontend
calls it first to learn whether the caller can query (and at what scope), so it
can render a friendly no-access screen instead of surfacing raw 403s."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.auth import access_scope, is_skills_user
from app.config import get_settings
from app.snapshot.store import get_snapshot_store

router = APIRouter()


class MeResponse(BaseModel):
    user_name: str
    user_rank: str
    user_teams: list[str]
    # "all" = full corp visibility; "self" = own characters only; "none" = no
    # access. can_query is the boolean the frontend gates on.
    scope: Literal["all", "self", "none"]
    can_query: bool


@router.get("/api/me")
async def me(request: Request) -> MeResponse:
    scope = await _resolve_scope(request)
    return MeResponse(
        user_name=getattr(request.state, "user_name", ""),
        user_rank=getattr(request.state, "user_rank", ""),
        user_teams=list(getattr(request.state, "user_teams", [])),
        scope=scope,
        can_query=scope != "none",
    )


async def _resolve_scope(request: Request) -> Literal["all", "self", "none"]:
    """Map the caller onto a coarse scope. Stays robust during an upstream
    outage: if the snapshot can't be fetched we can still honour full-visibility
    callers (allowlist-only), and report "none" for everyone else."""
    try:
        snapshot = await get_snapshot_store(get_settings()).get()
    except Exception:
        return "all" if is_skills_user(request) else "none"
    resolved = access_scope(request, snapshot)
    if resolved is None:
        return "none"
    return "all" if resolved == "all" else "self"
