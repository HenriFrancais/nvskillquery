"""FastAPI app entrypoint.

Lifespan: configure logging (snapshot warmup arrives with the data layer).
Middleware: NV Tools auth + CSP for iframe embedding.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.middleware import NVToolsAuthMiddleware
from app.observability.health import HEALTH
from app.observability.health import router as health_router
from app.observability.logging import configure_logging, log

# Repo root → frontend/dist. Present in production images (built by the Dockerfile);
# absent in dev where Vite serves the UI on its own port and proxies /api here.
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(level=settings.log_level)
    HEALTH.data_source = settings.data_source

    log.info("app.ready")
    try:
        yield
    finally:
        log.info("app.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    prefix = settings.url_prefix
    app = FastAPI(title="NV Skills", lifespan=lifespan)
    app.add_middleware(NVToolsAuthMiddleware)
    app.include_router(health_router, prefix=prefix)
    # Mount the built React bundle last so it acts as a catch-all for non-API paths.
    # API routes registered above take precedence; static assets fall through here.
    if _FRONTEND_DIST.is_dir():
        app.mount(
            f"{prefix}/" if prefix else "/",
            StaticFiles(directory=str(_FRONTEND_DIST), html=True),
            name="frontend",
        )
    return app


app = create_app()
