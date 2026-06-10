"""End-to-end API tests against the demo fixtures.

Demo data ground truth: 80 skills (ids 1000-1187 stepping by group), 50
users, 130 characters, 8 character types; skill 1000 = "Gunnery Operation".
"""

from __future__ import annotations

from tests.conftest import GATED_HEADERS, TEST_TOKEN, UNGATED_HEADERS

DOCTRINE_HEADERS = {
    "Authorization": f"Bearer {TEST_TOKEN}",
    "X-User-Name": "Doctrine Member",
    "X-User-Rank": "Member",
    "X-User-Teams": "Doctrine,FC",
}

SIMPLE_QUERY = {"query": {"kind": "skill", "skill_id": 1000, "min_level": 1}}


# --- gating matrix -----------------------------------------------------------


def test_me_reports_can_query_truth_table(client):
    me = client.get("/api/me", headers=GATED_HEADERS).json()
    assert me == {
        "user_name": "Gated User",
        "user_rank": "CEO",
        "user_teams": [],
        "can_query": True,
    }
    assert client.get("/api/me", headers=UNGATED_HEADERS).json()["can_query"] is False
    assert client.get("/api/me", headers=DOCTRINE_HEADERS).json()["can_query"] is True


def test_gated_endpoints_403_for_ungated_user(client):
    assert client.get("/api/catalog", headers=UNGATED_HEADERS).status_code == 403
    assert (
        client.post("/api/query", json=SIMPLE_QUERY, headers=UNGATED_HEADERS).status_code == 403
    )
    assert (
        client.get("/api/query/export.csv?q=x", headers=UNGATED_HEADERS).status_code == 403
    )


def test_gated_endpoints_ok_for_doctrine_team(client):
    assert client.get("/api/catalog", headers=DOCTRINE_HEADERS).status_code == 200
    assert (
        client.post("/api/query", json=SIMPLE_QUERY, headers=DOCTRINE_HEADERS).status_code
        == 200
    )


# --- catalog -----------------------------------------------------------------


def test_catalog_shape(client):
    cat = client.get("/api/catalog", headers=GATED_HEADERS).json()
    assert len(cat["skills"]) == 80
    assert len(cat["groups"]) == 10
    assert len(cat["char_types"]) == 8
    assert cat["snapshot_version"] == 1
    skill_1000 = next(s for s in cat["skills"] if s["skill_id"] == 1000)
    assert skill_1000["name"] == "Gunnery Operation"
    assert skill_1000["group_name"] == "Gunnery"
    # Some skill has prerequisites with names resolved server-side.
    with_prereqs = [s for s in cat["skills"] if s["prerequisites"]]
    assert with_prereqs
    assert all("name" in p for s in with_prereqs for p in s["prerequisites"])


# --- query -------------------------------------------------------------------


def test_query_happy_path(client):
    resp = client.post("/api/query", json=SIMPLE_QUERY, headers=GATED_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["totals"]["total_users"] == 50
    assert body["totals"]["total_characters"] == 130
    assert body["totals"]["users_with_matches"] == len(body["rows"]) > 0
    assert body["totals"]["total_matching_characters"] == sum(
        r["match_count"] for r in body["rows"]
    )
    # Sorted by match_count desc.
    counts = [r["match_count"] for r in body["rows"]]
    assert counts == sorted(counts, reverse=True)
    assert body["snapshot_version"] == 1


def test_query_nested_tree(client):
    nested = {
        "query": {
            "kind": "group",
            "op": "or",
            "children": [
                {"kind": "group", "op": "and", "children": [
                    {"kind": "skill", "skill_id": 1000, "min_level": 4},
                    {"kind": "skill", "skill_id": 1001, "min_level": 3},
                ]},
                {"kind": "char_type", "char_type": "Dreadnought"},
            ],
        }
    }
    resp = client.post("/api/query", json=nested, headers=GATED_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["totals"]["users_with_matches"] > 0


def test_query_structural_422(client):
    resp = client.post(
        "/api/query",
        json={"query": {"kind": "skill", "skill_id": 1000, "min_level": 9}},
        headers=GATED_HEADERS,
    )
    assert resp.status_code == 422


def test_query_unknown_refs_422(client):
    resp = client.post(
        "/api/query",
        json={"query": {"kind": "skill", "skill_id": 424242, "min_level": 1}},
        headers=GATED_HEADERS,
    )
    assert resp.status_code == 422
    assert "424242" in resp.json()["detail"]


def test_query_503_when_upstream_unavailable(make_client):
    client = make_client(DATA_SOURCE="real", SKILLS_API_URL="", USERS_API_URL="")
    resp = client.post("/api/query", json=SIMPLE_QUERY, headers=GATED_HEADERS)
    assert resp.status_code == 503
    assert resp.json()["detail"] == "snapshot_unavailable"


def test_query_result_cached_per_snapshot_version(client, monkeypatch):
    import app.api.query as query_mod

    calls = {"n": 0}
    real_run_query = query_mod.run_query

    def counting_run_query(*args, **kwargs):
        calls["n"] += 1
        return real_run_query(*args, **kwargs)

    monkeypatch.setattr(query_mod, "run_query", counting_run_query)
    for _ in range(3):
        assert (
            client.post("/api/query", json=SIMPLE_QUERY, headers=GATED_HEADERS).status_code
            == 200
        )
    assert calls["n"] == 1


# --- CSV export --------------------------------------------------------------


def test_csv_export(client):
    from app.queries.encode import encode_query
    from app.queries.tree import QUERY_NODE_ADAPTER

    q = encode_query(QUERY_NODE_ADAPTER.validate_python(SIMPLE_QUERY["query"]))
    resp = client.get(f"/api/query/export.csv?q={q}", headers=GATED_HEADERS)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    disposition = resp.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="skillquery-')
    lines = resp.text.strip().splitlines()
    header = lines[0].split(",")
    assert header == [
        "user_name",
        "main_character",
        "main_character_type",
        "main_character_matches",
        "match_count",
        "total_characters",
        "matching_characters",
    ]
    # Row count matches the JSON result for the same query.
    json_rows = client.post("/api/query", json=SIMPLE_QUERY, headers=GATED_HEADERS).json()[
        "rows"
    ]
    assert len(lines) - 1 == len(json_rows)


def test_csv_export_bad_q_422(client):
    resp = client.get("/api/query/export.csv?q=!!!", headers=GATED_HEADERS)
    assert resp.status_code == 422
