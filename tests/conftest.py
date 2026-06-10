"""Shared test fixtures.

``make_client`` boots the FastAPI app with env overrides and demo data so
tests don't hit the network or need a real ``.env``/``config.toml``. The
settings/config singletons are lru_cached, so every boot clears them.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.query import reset_query_cache_for_tests
from app.config import get_app_config, get_settings
from app.observability.health import HEALTH
from app.snapshot.store import reset_snapshot_store_for_tests

TEST_TOKEN = "test-token"

# Headers the NV Tools proxy would inject for a user who passes the default
# visibility gate (rank CEO).
GATED_HEADERS = {
    "Authorization": f"Bearer {TEST_TOKEN}",
    "X-User-Name": "Gated User",
    "X-User-Rank": "CEO",
    "X-User-Teams": "",
    "X-User-Main-Character-Id": "90000001",
}

# Headers for an authenticated user who does NOT pass the gate.
UNGATED_HEADERS = {
    "Authorization": f"Bearer {TEST_TOKEN}",
    "X-User-Name": "Plain Member",
    "X-User-Rank": "Member",
    "X-User-Teams": "Recruitment",
    "X-User-Main-Character-Id": "90000002",
}


def _clear_caches() -> None:
    get_settings.cache_clear()
    get_app_config.cache_clear()
    reset_snapshot_store_for_tests()
    reset_query_cache_for_tests()
    HEALTH.snapshot_loaded = False
    HEALTH.snapshot_version = 0
    HEALTH.snapshot_fetched_at = 0.0
    HEALTH.data_source = ""


@pytest.fixture
def make_client(monkeypatch):
    """Factory: boot the app with env overrides, yield a TestClient."""

    clients: list[TestClient] = []

    def _make(**env: str) -> TestClient:
        defaults = {
            "NV_TOKEN": TEST_TOKEN,
            "DEV_MODE": "0",
            "DATA_SOURCE": "demo",
            "URL_PREFIX": "",
        }
        defaults.update(env)
        for key, value in defaults.items():
            monkeypatch.setenv(key, value)
        _clear_caches()
        from app.main import create_app

        client = TestClient(create_app())
        client.__enter__()
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.__exit__(None, None, None)
    _clear_caches()


@pytest.fixture
def client(make_client) -> TestClient:
    """Default app: demo data, real auth (no DEV_MODE)."""
    return make_client()
