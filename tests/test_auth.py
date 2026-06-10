"""Bearer-token middleware behaviour. Routing happens after auth, so even a
nonexistent path exercises the middleware: 401 without a valid bearer, 404
with one."""

from __future__ import annotations

from tests.conftest import GATED_HEADERS, TEST_TOKEN


def test_missing_bearer_rejected(client):
    resp = client.get("/api/anything")
    assert resp.status_code == 401
    assert resp.json() == {"error": "unauthorized"}


def test_wrong_bearer_rejected(client):
    resp = client.get("/api/anything", headers={"Authorization": "Bearer wrong-token"})
    assert resp.status_code == 401


def test_valid_bearer_passes_middleware(client):
    resp = client.get("/api/anything", headers=GATED_HEADERS)
    assert resp.status_code == 404  # authenticated; route just doesn't exist yet


def test_401_still_sets_csp(client):
    resp = client.get("/api/anything")
    assert (
        resp.headers["content-security-policy"]
        == "frame-ancestors https://tools.novacancies.space"
    )


def test_dev_mode_injects_identity(make_client):
    client = make_client(DEV_MODE="1", DEV_USER_RANK="CEO")
    resp = client.get("/api/anything")  # no Authorization header at all
    assert resp.status_code == 404  # dev injection authenticated the request


def test_dev_mode_real_token_still_wins(make_client):
    client = make_client(DEV_MODE="1")
    resp = client.get("/api/anything", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 404
    resp = client.get("/api/anything", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401
