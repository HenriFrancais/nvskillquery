"""Auth middleware (NV Tools bearer + X-User-* identity) + CSP header for
iframe embedding.

Every path except /healthz requires Authorization: Bearer <NV_TOKEN>; the
X-User-* headers injected by the NV Tools reverse proxy populate
request.state. DEV_MODE auto-injects fakes so local curls/browsers work.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

_CSP = "frame-ancestors https://tools.novacancies.space"


def _open_paths(prefix: str) -> set[str]:
    return {f"{prefix}/healthz"}


class NVToolsAuthMiddleware(BaseHTTPMiddleware):
    """Validate the NV Tools bearer token and attach caller identity to request.state."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = get_settings()
        path = request.url.path
        prefix = settings.url_prefix

        # Read directly from scope so we don't materialise Starlette's cached Headers
        # before we have a chance to inject dev-mode credentials.
        scope_headers: list[tuple[bytes, bytes]] = list(request.scope.get("headers", []))
        headers_lookup = {
            name.decode("latin-1").lower(): value.decode("latin-1") for name, value in scope_headers
        }

        if path in _open_paths(prefix):
            response = await call_next(request)
            response.headers["content-security-policy"] = _CSP
            return response

        if settings.dev_mode and "authorization" not in headers_lookup:
            scope_headers = _inject_dev_headers(
                scope_headers,
                token=settings.nv_token,
                rank=settings.dev_user_rank,
                teams=settings.dev_user_teams,
            )
            request.scope["headers"] = scope_headers
            headers_lookup = {
                name.decode("latin-1").lower(): value.decode("latin-1")
                for name, value in scope_headers
            }
        expected = f"Bearer {settings.nv_token}"
        if headers_lookup.get("authorization") != expected:
            return JSONResponse(
                {"error": "unauthorized"},
                status_code=401,
                headers={"content-security-policy": _CSP},
            )
        request.state.user_name = headers_lookup.get("x-user-name", "")
        request.state.user_rank = headers_lookup.get("x-user-rank", "")
        request.state.user_teams = [
            t.strip() for t in headers_lookup.get("x-user-teams", "").split(",") if t.strip()
        ]
        request.state.user_main_character_id = headers_lookup.get("x-user-main-character-id", "")

        response = await call_next(request)
        response.headers["content-security-policy"] = _CSP
        return response


def _inject_dev_headers(
    headers: list[tuple[bytes, bytes]],
    token: str,
    rank: str = "",
    teams: str = "",
) -> list[tuple[bytes, bytes]]:
    """Add fake auth + user headers to the ASGI scope (dev mode only).

    Rank/teams default to ``Member`` / ``Admin`` (router convention); note that
    identity does NOT pass the skill-query gate — set ``DEV_USER_RANK`` /
    ``DEV_USER_TEAMS`` to test the gated paths.
    """
    effective_rank = rank.strip() or "Member"
    effective_teams = teams.strip() or "Admin"
    extra = [
        (b"authorization", f"Bearer {token}".encode()),
        (b"x-user-name", b"Test User"),
        (b"x-user-rank", effective_rank.encode("latin-1")),
        (b"x-user-teams", effective_teams.encode("latin-1")),
        (b"x-user-main-character-id", b"0"),
    ]
    existing_names = {name for name, _ in headers}
    return [*headers, *[(n, v) for n, v in extra if n not in existing_names]]
