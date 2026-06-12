"""FastAPI app entrypoint.

Lifespan: configure logging, warm the snapshot store off the user's path.
Middleware: NV Tools auth + CSP for iframe embedding.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.catalog import router as catalog_router
from app.api.doctrines import router as doctrines_router
from app.api.meta import router as meta_router
from app.api.query import router as query_router
from app.config import get_settings
from app.middleware import NVToolsAuthMiddleware
from app.observability.health import HEALTH
from app.observability.health import router as health_router
from app.observability.logging import configure_logging, log
from app.snapshot.store import get_snapshot_store

# Repo root → frontend/dist. Present in production images (built by the Dockerfile);
# absent in dev where Vite serves the UI on its own port and proxies /api here.
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(level=settings.log_level)
    HEALTH.data_source = settings.data_source

    # Warm the snapshot off the user's path: the two upstream fetches can be
    # slow, and without this the first query after boot would block on them.
    async def _warm_snapshot() -> None:
        try:
            await get_snapshot_store(settings).get()
        except Exception as exc:
            log.warning("snapshot.warmup_failed", error=str(exc))

    warmup = asyncio.create_task(_warm_snapshot(), name="snapshot-warmup")

    log.info("app.ready")
    try:
        yield
    finally:
        warmup.cancel()
        log.info("app.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    prefix = settings.url_prefix
    app = FastAPI(title="NV Skills", lifespan=lifespan)
    app.add_middleware(NVToolsAuthMiddleware)
    app.include_router(health_router, prefix=prefix)
    app.include_router(meta_router, prefix=prefix)
    app.include_router(catalog_router, prefix=prefix)
    app.include_router(doctrines_router, prefix=prefix)
    app.include_router(query_router, prefix=prefix)
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
