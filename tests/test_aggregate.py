"""Per-user aggregation: rows, ordering, totals, pool filter, build rules."""

from __future__ import annotations

from app.queries.aggregate import run_query
from app.queries.tree import QUERY_NODE_ADAPTER
from tests.helpers import CATALOG_SKILLS, simple_snapshot, snapshot_from


def q(data: dict) -> object:
    return QUERY_NODE_ADAPTER.validate_python(data)


SKILL1_AT_3 = {"kind": "skill", "skill_id": 1, "min_level": 3}


def test_rows_and_totals():
    snap = simple_snapshot()
    resp = run_query(snap, q(SKILL1_AT_3))
    # Alice: both chars have skill 1 >= 3; Carol: only the alt; Bob: no match.
    assert [r.user_name for r in resp.rows] == ["Alice", "Carol"]
    assert [r.match_count for r in resp.rows] == [2, 1]
    assert resp.totals.users_with_matches == 2
    assert resp.totals.total_matching_characters == 3
    assert resp.totals.total_users == 3
    assert resp.totals.total_characters == 5


def test_main_character_match_flag():
    snap = simple_snapshot()
    resp = run_query(snap, q(SKILL1_AT_3))
    alice = next(r for r in resp.rows if r.user_name == "Alice")
    carol = next(r for r in resp.rows if r.user_name == "Carol")
    assert alice.main_character.matches is True
    assert carol.main_character.matches is False
    assert carol.main_character.name == "Carol"
    assert [c.name for c in carol.matching_characters] == ["Carol II"]


def test_tie_break_by_user_name():
    snap = simple_snapshot()
    # One matching character each for Alice (alt @4) and Bob (main @2).
    resp = run_query(snap, q({"kind": "skill", "skill_id": 2, "min_level": 2}))
    assert [r.user_name for r in resp.rows] == ["Alice", "Bob"]
    assert [r.match_count for r in resp.rows] == [1, 1]


def test_include_non_matching_appends_after_matches():
    snap = simple_snapshot()
    resp = run_query(snap, q(SKILL1_AT_3), include_non_matching=True)
    assert [r.user_name for r in resp.rows] == ["Alice", "Carol", "Bob"]
    assert resp.rows[-1].match_count == 0
    # Totals still count only matching users.
    assert resp.totals.users_with_matches == 2


def test_no_matches_at_all():
    snap = simple_snapshot()
    resp = run_query(snap, q({"kind": "skill", "skill_id": 2, "min_level": 5}))
    assert resp.rows == []
    assert resp.totals.users_with_matches == 0
    assert resp.totals.total_matching_characters == 0


def test_snapshot_metadata_passthrough():
    snap = simple_snapshot()
    resp = run_query(snap, q(SKILL1_AT_3))
    assert resp.snapshot_version == 1
    assert resp.snapshot_fetched_at == "1970-01-01T00:00:00+00:00"


# ---- group pool filter ----


def test_pool_scopes_matching_and_counts():
    snap = simple_snapshot()
    # Alice matches with both chars overall, but only the Home main is in pool.
    resp = run_query(snap, q(SKILL1_AT_3), groups=["Home"])
    alice = next(r for r in resp.rows if r.user_name == "Alice")
    assert alice.match_count == 1
    assert alice.total_characters == 1
    assert [c.name for c in alice.matching_characters] == ["Alice"]
    assert all(c.group == "Home" for c in alice.matching_characters)


def test_zero_pool_user_dropped():
    # Bob has no Strat characters at all.
    snap = simple_snapshot()
    resp = run_query(snap, q({"kind": "skill", "skill_id": 1, "min_level": 1}),
                     groups=["Strat"])
    assert [r.user_name for r in resp.rows] == ["Alice"]


def test_zero_pool_user_included_when_non_matching():
    snap = simple_snapshot()
    resp = run_query(snap, q({"kind": "skill", "skill_id": 1, "min_level": 1}),
                     groups=["Strat"], include_non_matching=True)
    rows = {r.user_name: r for r in resp.rows}
    assert set(rows) == {"Alice", "Bob", "Carol"}
    assert rows["Bob"].match_count == 0
    assert rows["Bob"].total_characters == 0


def test_main_outside_pool_shown_not_matching():
    snap = simple_snapshot()
    # Carol's main is Farm; the Home pool contains only her matching alt.
    resp = run_query(snap, q(SKILL1_AT_3), groups=["Home"])
    carol = next(r for r in resp.rows if r.user_name == "Carol")
    assert carol.main_character.name == "Carol"
    assert carol.main_character.matches is False
    assert carol.total_characters == 1


def test_totals_are_pool_relative():
    snap = simple_snapshot()
    resp = run_query(snap, q(SKILL1_AT_3), groups=["Home"])
    # Pool = Alice(101), Bob(201), Carol II(302): 3 chars across 3 users.
    assert resp.totals.total_characters == 3
    assert resp.totals.total_users == 3
    # Matches in pool: Alice main @5, Carol II @4.
    assert resp.totals.users_with_matches == 2
    assert resp.totals.total_matching_characters == 2


def test_empty_groups_means_all():
    snap = simple_snapshot()
    assert run_query(snap, q(SKILL1_AT_3), groups=[]) == run_query(snap, q(SKILL1_AT_3))


# ---- snapshot build rules ----


def test_build_drops_orphans_and_fixes_bad_main():
    snap = snapshot_from(
        CATALOG_SKILLS,
        # skills API: flat list per character
        [
            {"character_id": 999, "main_character_id": 701, "skills": {}},  # orphan
            {"character_id": 701, "main_character_id": 701, "skills": {}},
        ],
        # users API: flat list
        [
            # main_character_id points at a character not in the list → falls
            # back to the first character (701), which becomes the user key.
            {"user_name": "Dave", "main_character_id": 12345, "characters": [
                {"character_id": 701, "character_name": "Dave"},
            ]},
            # zero characters → dropped entirely
            {"user_name": "Eve", "main_character_id": 1, "characters": []},
        ],
    )
    assert set(snap.users) == {701}
    assert snap.users[701].main_character_id == 701
    assert snap.characters[701].is_main
    # Pool is inert: a single default group.
    assert snap.character_groups == ("All",)
    assert snap.characters[701].group == "All"


def test_build_drops_unknown_trained_skills():
    snap = snapshot_from(
        CATALOG_SKILLS,
        [{"character_id": 101, "main_character_id": 101,
          "skills": {"1": 5, "999": 3}}],  # 999 not in SDE catalogue
        [{"user_name": "Alice", "main_character_id": 101, "characters": [
            {"character_id": 101, "character_name": "Alice"}]}],
    )
    assert snap.characters[101].skill_levels == {1: 5}


def test_snapshot_carries_sde_build_number():
    assert simple_snapshot().sde_build_number == 1
