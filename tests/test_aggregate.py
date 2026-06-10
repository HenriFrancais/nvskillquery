"""Per-user aggregation: rows, ordering, totals, snapshot build rules."""

from __future__ import annotations

from app.queries.aggregate import run_query
from app.queries.tree import QUERY_NODE_ADAPTER
from tests.helpers import simple_snapshot, snapshot_from


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
    # Matches one character for everyone who has a Subcap: Alice, Bob, Carol.
    resp = run_query(snap, q({"kind": "char_type", "char_type": "Subcap"}))
    assert [r.user_name for r in resp.rows] == ["Alice", "Bob", "Carol"]


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


def test_build_drops_orphans_and_fixes_bad_main():
    snap = snapshot_from(
        {
            "skills": [],
            "users": [
                # user 7 exists; char 999 doesn't → orphan char dropped
                {"user_id": 7, "characters": [{"character_id": 999, "skills": []}]},
                # user 8 doesn't exist at all → orphan user dropped
                {"user_id": 8, "characters": [{"character_id": 701, "skills": []}]},
            ],
        },
        {
            "character_types": [],
            "users": [
                # main_character_id points at a character not in the list
                {"user_id": 7, "user_name": "Dave", "main_character_id": 12345, "characters": [
                    {"character_id": 701, "name": "Dave", "character_type": "Subcap"},
                ]},
                # zero characters → dropped entirely
                {"user_id": 9, "user_name": "Eve", "main_character_id": 1, "characters": []},
            ],
        },
    )
    assert set(snap.users) == {7}
    assert snap.users[7].main_character_id == 701
    assert snap.characters[701].is_main
    # character_types fell back to the distinct set seen on characters.
    assert snap.char_types == ("Subcap",)
