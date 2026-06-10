"""Query tree evaluation against single characters (skills-only)."""

from __future__ import annotations

from app.queries.evaluate import character_matches
from app.queries.tree import QUERY_NODE_ADAPTER
from tests.helpers import char


def q(data: dict) -> object:
    return QUERY_NODE_ADAPTER.validate_python(data)


def test_skill_condition_min_level_is_gte():
    node = q({"kind": "skill", "skill_id": 1, "min_level": 3})
    assert character_matches(node, char(skill_levels={1: 3}))
    assert character_matches(node, char(skill_levels={1: 5}))
    assert not character_matches(node, char(skill_levels={1: 2}))


def test_untrained_skill_is_level_zero():
    node = q({"kind": "skill", "skill_id": 99, "min_level": 1})
    assert not character_matches(node, char(skill_levels={1: 5}))


def test_and_group():
    node = q({
        "kind": "group", "op": "and", "children": [
            {"kind": "skill", "skill_id": 1, "min_level": 3},
            {"kind": "skill", "skill_id": 2, "min_level": 2},
        ],
    })
    assert character_matches(node, char(skill_levels={1: 3, 2: 2}))
    assert not character_matches(node, char(skill_levels={1: 3}))


def test_or_group():
    node = q({
        "kind": "group", "op": "or", "children": [
            {"kind": "skill", "skill_id": 1, "min_level": 5},
            {"kind": "skill", "skill_id": 2, "min_level": 1},
        ],
    })
    assert character_matches(node, char(skill_levels={1: 5}))
    assert character_matches(node, char(skill_levels={2: 1}))
    assert not character_matches(node, char(skill_levels={1: 4}))


def test_nested_and_or():
    # (skill1 >= 4 AND skill2 >= 3) OR skill3 >= 1
    node = q({
        "kind": "group", "op": "or", "children": [
            {"kind": "group", "op": "and", "children": [
                {"kind": "skill", "skill_id": 1, "min_level": 4},
                {"kind": "skill", "skill_id": 2, "min_level": 3},
            ]},
            {"kind": "skill", "skill_id": 3, "min_level": 1},
        ],
    })
    assert character_matches(node, char(skill_levels={1: 4, 2: 3}))
    assert character_matches(node, char(skill_levels={3: 1}))
    assert not character_matches(node, char(skill_levels={1: 4, 2: 2}))
    assert not character_matches(node, char(skill_levels={2: 5}))
