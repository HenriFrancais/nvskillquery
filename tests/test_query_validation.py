"""Structural and semantic validation of query trees and group pools."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.queries.tree import (
    MAX_DEPTH,
    MAX_NODES,
    QUERY_NODE_ADAPTER,
    QueryValidationError,
    validate_groups,
    validate_limits,
    validate_refs,
)
from tests.helpers import simple_snapshot


def parse(data: dict) -> object:
    return QUERY_NODE_ADAPTER.validate_python(data)


@pytest.mark.parametrize(
    "bad",
    [
        {"kind": "nope"},
        {"kind": "skill", "skill_id": 1},  # missing min_level
        {"kind": "skill", "skill_id": 1, "min_level": 0},
        {"kind": "skill", "skill_id": 1, "min_level": 6},
        {"kind": "skill", "skill_id": 1, "min_level": 3, "extra": True},
        # char_type conditions were removed; legacy trees must be rejected.
        {"kind": "char_type", "char_type": "Home"},
        {"kind": "group", "op": "and", "children": []},
        {"kind": "group", "op": "xor", "children": [{"kind": "skill", "skill_id": 1, "min_level": 1}]},
        {"kind": "group", "op": "and"},
    ],
)
def test_structurally_invalid_trees_rejected(bad: dict):
    with pytest.raises(ValidationError):
        parse(bad)


def _nested(depth: int) -> dict:
    node: dict = {"kind": "skill", "skill_id": 1, "min_level": 1}
    for _ in range(depth - 1):
        node = {"kind": "group", "op": "and", "children": [node]}
    return node


def test_depth_at_limit_ok():
    validate_limits(parse(_nested(MAX_DEPTH)))


def test_depth_over_limit_rejected():
    with pytest.raises(QueryValidationError, match="depth"):
        validate_limits(parse(_nested(MAX_DEPTH + 1)))


def test_node_count_over_limit_rejected():
    wide = {
        "kind": "group",
        "op": "or",
        "children": [{"kind": "skill", "skill_id": i, "min_level": 1} for i in range(MAX_NODES)],
    }
    with pytest.raises(QueryValidationError, match="size"):
        validate_limits(parse(wide))


def test_unknown_skill_refs_listed():
    snap = simple_snapshot()
    tree = parse({
        "kind": "group", "op": "and", "children": [
            {"kind": "skill", "skill_id": 999, "min_level": 1},
            {"kind": "skill", "skill_id": 1, "min_level": 1},
        ],
    })
    with pytest.raises(QueryValidationError) as exc:
        validate_refs(tree, snap)
    assert "999" in str(exc.value)


def test_known_refs_pass():
    snap = simple_snapshot()
    validate_refs(parse({"kind": "skill", "skill_id": 1, "min_level": 5}), snap)


def test_unknown_groups_listed():
    snap = simple_snapshot()
    with pytest.raises(QueryValidationError) as exc:
        validate_groups(["Home", "Nope", "Wrong"], snap)
    assert "Nope" in str(exc.value)
    assert "Wrong" in str(exc.value)


def test_known_groups_pass():
    snap = simple_snapshot()
    validate_groups(["Home", "Alpha"], snap)
    validate_groups([], snap)
