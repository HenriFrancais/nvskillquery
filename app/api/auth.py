"""Shared in-app authorization helpers.

The skill-query gate is a deployment-configured allowlist (AppConfig
visibility_ranks/visibility_teams). Being on the allowlist is the single
gate: every query/catalog endpoint uses it, /api/me reports it so the
frontend can render a friendly no-access screen.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, Request

from app.config import get_app_config


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
    cfg = get_app_config()
    return has_any_role(request, cfg.visibility_ranks, cfg.visibility_teams)


def require_skills(request: Request) -> None:
    if not is_skills_user(request):
        raise HTTPException(status_code=403, detail="skills_forbidden")
