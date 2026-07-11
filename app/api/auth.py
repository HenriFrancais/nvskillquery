"""Shared in-app authorization helpers.

Two tiers of access:

  - **Full visibility** — callers whose rank/team is on the deployment
    allowlist (AppConfig visibility_ranks/visibility_teams). They may query
    across every corp member.
  - **Self visibility** — any other authenticated caller whose main character
    maps to a roster member. They may query, but results are scoped to their
    own characters.

A caller who is neither (no roster match) has no access at all. ``/api/me``
reports the resolved scope so the frontend can render a friendly no-access
screen instead of surfacing raw 403s.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from fastapi import HTTPException, Request

from app.config import get_app_config, get_settings
from app.snapshot.models import Snapshot
from app.snapshot.store import get_snapshot_store

# "all" = full corp visibility; an int = a single user_id (self-scope);
# None = no access.
AccessScope = Literal["all"] | int | None


def has_any_role(
    request: Request,
    ranks: Iterable[str],
    teams: Iterable[str],
) -> bool:
    """True iff the caller's rank matches any in `ranks`, or any of their
    teams appears in `teams`. Empty allowlists return False — a misconfigured
    or unset allowlist locks the feature down rather than opening it up."""
    rank_set = {r for r in ranks if r}
    team_set = {t for t in teams if t}
    if not rank_set and not team_set:
        return False
    user_rank = getattr(request.state, "user_rank", "") or ""
    user_teams = getattr(request.state, "user_teams", []) or []
    if user_rank and user_rank in rank_set:
        return True
    return any(t in team_set for t in user_teams)


def is_skills_user(request: Request) -> bool:
    """True iff the caller has full-corp visibility (on the rank/team allowlist)."""
    cfg = get_app_config()
    return has_any_role(request, cfg.visibility_ranks, cfg.visibility_teams)


def caller_user_id(request: Request) -> int | None:
    """The caller's own user_id, parsed from the proxy-injected main character
    id. Returns None when the header is empty or non-numeric. (The snapshot's
    synthetic user_id equals the member's main_character_id.)"""
    raw = getattr(request.state, "user_main_character_id", "") or ""
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def access_scope(request: Request, snapshot: Snapshot) -> AccessScope:
    """Resolve the caller's visibility against the current roster:
    ``"all"`` for allowlisted callers, their own ``user_id`` for a plain
    roster member, or ``None`` when they match no member."""
    if is_skills_user(request):
        return "all"
    uid = caller_user_id(request)
    if uid is not None and uid in snapshot.users:
        return uid
    return None


async def require_access(request: Request) -> None:
    """Router dependency: allow full-visibility callers and roster members;
    reject everyone else with 403. Fetches the current snapshot (503 while the
    upstream is unavailable on cold start) to check roster membership."""
    store = get_snapshot_store(get_settings())
    try:
        snapshot = await store.get()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="snapshot_unavailable") from exc
    if access_scope(request, snapshot) is None:
        raise HTTPException(status_code=403, detail="forbidden")
