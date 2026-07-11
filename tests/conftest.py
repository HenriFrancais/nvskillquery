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
from app.sde.catalog import reset_sde_catalog_for_tests
from app.snapshot.store import reset_snapshot_store_for_tests

TEST_TOKEN = "test-token"

# Headers the NV Tools proxy would inject for a user with FULL corp visibility
# (on the rank/team allowlist, here rank CEO). Scope = "all".
GATED_HEADERS = {
    "Authorization": f"Bearer {TEST_TOKEN}",
    "X-User-Name": "Gated User",
    "X-User-Rank": "CEO",
    "X-User-Teams": "",
    "X-User-Main-Character-Id": "90000001",
}

# A plain roster member (not on the allowlist) whose main maps to a demo user
# (Raven, 90000007, 3 characters). Scope = "self": query works, but results are
# limited to their own characters.
MEMBER_HEADERS = {
    "Authorization": f"Bearer {TEST_TOKEN}",
    "X-User-Name": "Raven",
    "X-User-Rank": "Member",
    "X-User-Teams": "",
    "X-User-Main-Character-Id": "90000007",
}
MEMBER_USER_ID = 90000007

# An authenticated caller whose main matches NO roster member (non-member).
# Scope = "none": every gated endpoint returns 403.
UNGATED_HEADERS = {
    "Authorization": f"Bearer {TEST_TOKEN}",
    "X-User-Name": "Random Person",
    "X-User-Rank": "Member",
    "X-User-Teams": "Recruitment",
    "X-User-Main-Character-Id": "70000000",
}


def _clear_caches() -> None:
    get_settings.cache_clear()
    get_app_config.cache_clear()
    reset_snapshot_store_for_tests()
    reset_query_cache_for_tests()
    reset_sde_catalog_for_tests()
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
            # Force the committed demo fallback catalogue: a developer's local
            # var/sde (real SDE) must not leak into test ground truth.
            "SDE_DIR": "/nonexistent-sde-for-tests",
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
