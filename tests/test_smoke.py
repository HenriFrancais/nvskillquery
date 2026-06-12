"""Boot + healthz smoke tests."""

from __future__ import annotations


def test_healthz_open_without_auth(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data_source"] == "demo"


def test_healthz_sets_csp_header(client):
    resp = client.get("/healthz")
    assert (
        resp.headers["content-security-policy"]
        == "frame-ancestors https://tools.novacancies.space https://novacancies.space"
    )


def test_healthz_respects_url_prefix(make_client):
    client = make_client(URL_PREFIX="/skillquery")
    assert client.get("/skillquery/healthz").status_code == 200
    # The unprefixed path is no longer open and falls through to auth.
    assert client.get("/healthz").status_code == 401
