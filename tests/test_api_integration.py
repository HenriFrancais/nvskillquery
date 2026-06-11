"""End-to-end API tests against the demo fixtures.

Demo ground truth is derived from the committed fixture files rather than
hardcoded: the skill catalogue is a sampled subset of the REAL SDE (see
scripts/gen_demo_fixtures.py), so ids and counts change when regenerated.
50 users and a single inert "All" pool group are generator constants.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from tests.conftest import GATED_HEADERS, TEST_TOKEN, UNGATED_HEADERS

DATA_DEMO = Path(__file__).resolve().parent.parent / "data_demo"
DEMO_CATALOG = json.loads((DATA_DEMO / "sde_skills.json").read_text())
DEMO_TRAINED = json.loads((DATA_DEMO / "skills_api.json").read_text())

# The most commonly trained skill across the demo characters — guaranteed to
# produce matches.
COMMON_SKILL_ID = Counter(
    int(sid)
    for c in DEMO_TRAINED
    for sid in c["skills"]
).most_common(1)[0][0]

DOCTRINE_HEADERS = {
    "Authorization": f"Bearer {TEST_TOKEN}",
    "X-User-Name": "Doctrine Member",
    "X-User-Rank": "Member",
    "X-User-Teams": "Doctrine,FC",
}

SIMPLE_QUERY = {"query": {"kind": "skill", "skill_id": COMMON_SKILL_ID, "min_level": 1}}


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
    assert len(cat["skills"]) == len(DEMO_CATALOG["skills"])
    expected_groups = {s["group_id"] for s in DEMO_CATALOG["skills"]}
    assert len(cat["groups"]) == len(expected_groups)
    assert cat["character_groups"] == ["All"]
    assert "char_types" not in cat
    assert cat["sde_build_number"] == DEMO_CATALOG["sde_build_number"]
    assert cat["snapshot_version"] == 1
    # Names/groups come straight from the (real-SDE-derived) catalogue file.
    expected = next(s for s in DEMO_CATALOG["skills"] if s["skill_id"] == COMMON_SKILL_ID)
    served = next(s for s in cat["skills"] if s["skill_id"] == COMMON_SKILL_ID)
    assert served["name"] == expected["name"]
    assert served["group_name"] == expected["group_name"]
    # Some skill has prerequisites with names resolved server-side (the
    # fallback catalogue includes the prerequisite closure, so every prereq
    # name must resolve to a real name, never the #id placeholder).
    with_prereqs = [s for s in cat["skills"] if s["prerequisites"]]
    assert with_prereqs
    assert all(
        not p["name"].startswith("#") for s in with_prereqs for p in s["prerequisites"]
    )


# --- query -------------------------------------------------------------------


def test_query_happy_path(client):
    n_chars = len(DEMO_TRAINED)
    resp = client.post("/api/query", json=SIMPLE_QUERY, headers=GATED_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["totals"]["total_users"] == 50
    assert body["totals"]["total_characters"] == n_chars
    assert body["totals"]["users_with_matches"] == len(body["rows"]) > 0
    assert body["totals"]["total_matching_characters"] == sum(
        r["match_count"] for r in body["rows"]
    )
    # Sorted by match_count desc.
    counts = [r["match_count"] for r in body["rows"]]
    assert counts == sorted(counts, reverse=True)
    assert body["snapshot_version"] == 1


def test_query_nested_tree(client):
    ids = [s["skill_id"] for s in DEMO_CATALOG["skills"][:3]]
    nested = {
        "query": {
            "kind": "group",
            "op": "or",
            "children": [
                {"kind": "group", "op": "and", "children": [
                    {"kind": "skill", "skill_id": ids[0], "min_level": 4},
                    {"kind": "skill", "skill_id": ids[1], "min_level": 3},
                ]},
                {"kind": "skill", "skill_id": COMMON_SKILL_ID, "min_level": 1},
            ],
        }
    }
    resp = client.post("/api/query", json=nested, headers=GATED_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["totals"]["users_with_matches"] > 0


def test_query_char_type_node_rejected(client):
    legacy = {"query": {"kind": "char_type", "char_type": "Home"}}
    resp = client.post("/api/query", json=legacy, headers=GATED_HEADERS)
    assert resp.status_code == 422


def test_query_groups_scope_pool(client):
    full = client.post("/api/query", json=SIMPLE_QUERY, headers=GATED_HEADERS).json()
    home = client.post(
        "/api/query",
        json={**SIMPLE_QUERY, "groups": ["All"]},
        headers=GATED_HEADERS,
    ).json()
    assert home["totals"]["total_characters"] <= full["totals"]["total_characters"]
    assert home["totals"]["total_characters"] > 0
    for row in home["rows"]:
        assert all(c["group"] == "All" for c in row["matching_characters"])
        assert row["match_count"] <= row["total_characters"]
    # Every group filter result is a subset of the unfiltered result.
    assert home["totals"]["total_matching_characters"] <= full["totals"][
        "total_matching_characters"
    ]


def test_query_unknown_group_422(client):
    resp = client.post(
        "/api/query",
        json={**SIMPLE_QUERY, "groups": ["Dreadnought"]},
        headers=GATED_HEADERS,
    )
    assert resp.status_code == 422
    assert "Dreadnought" in resp.json()["detail"]


def test_query_structural_422(client):
    resp = client.post(
        "/api/query",
        json={"query": {"kind": "skill", "skill_id": COMMON_SKILL_ID, "min_level": 9}},
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
    client = make_client(DATA_SOURCE="real", NV_API_URL="")
    resp = client.post("/api/query", json=SIMPLE_QUERY, headers=GATED_HEADERS)
    assert resp.status_code == 503
    assert resp.json()["detail"] == "snapshot_unavailable"


def test_query_result_cached_per_snapshot_version_and_groups(client, monkeypatch):
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
    # A different pool is a different cache entry.
    body = {**SIMPLE_QUERY, "groups": ["All"]}
    assert client.post("/api/query", json=body, headers=GATED_HEADERS).status_code == 200
    assert calls["n"] == 2


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
        "main_character_group",
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


def test_csv_export_groups_param(client):
    from app.queries.encode import encode_query
    from app.queries.tree import QUERY_NODE_ADAPTER

    q = encode_query(QUERY_NODE_ADAPTER.validate_python(SIMPLE_QUERY["query"]))
    full = client.get(f"/api/query/export.csv?q={q}", headers=GATED_HEADERS)
    home = client.get(f"/api/query/export.csv?q={q}&g=All", headers=GATED_HEADERS)
    assert home.status_code == 200
    assert len(home.text.strip().splitlines()) <= len(full.text.strip().splitlines())
    # Unknown group name → 422, same as the POST endpoint.
    bad = client.get(f"/api/query/export.csv?q={q}&g=Nope", headers=GATED_HEADERS)
    assert bad.status_code == 422


def test_csv_export_bad_q_422(client):
    resp = client.get("/api/query/export.csv?q=!!!", headers=GATED_HEADERS)
    assert resp.status_code == 422
