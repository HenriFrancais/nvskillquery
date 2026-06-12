"""Minimal additional skill points for a character to satisfy a query tree.

Covers the SP table, prerequisite closure, AND dedup / max-level merge, and
OR cheapest-branch selection. Pure functions — no snapshot machinery."""

from __future__ import annotations

from collections.abc import Mapping

from app.queries.sp_cost import character_gap, skill_points
from app.queries.tree import QUERY_NODE_ADAPTER
from app.snapshot.models import SkillDef
from app.sources.payloads import SkillPrereq
from tests.helpers import char


def q(data: dict) -> object:
    return QUERY_NODE_ADAPTER.validate_python(data)


def skills(*defs: dict) -> Mapping[int, SkillDef]:
    """Build a skill catalogue from compact dicts. Each: id, optional rank
    (default 1) and prerequisites [(skill_id, level), ...]."""
    out: dict[int, SkillDef] = {}
    for d in defs:
        out[d["id"]] = SkillDef(
            skill_id=d["id"],
            name=f"Skill {d['id']}",
            group_id=1,
            group_name="G",
            rank=d.get("rank", 1),
            prerequisites=tuple(
                SkillPrereq(skill_id=s, level=lvl) for s, lvl in d.get("prereqs", [])
            ),
        )
    return out


# --- the SP table -----------------------------------------------------------

def test_skill_points_table_rank_one():
    assert skill_points(1, 0) == 0
    assert skill_points(1, 1) == 250
    assert skill_points(1, 2) == 1414
    assert skill_points(1, 3) == 8000
    assert skill_points(1, 4) == 45255
    assert skill_points(1, 5) == 256000


def test_skill_points_scales_with_rank():
    assert skill_points(5, 5) == 256000 * 5
    assert skill_points(3, 3) == 8000 * 3


# --- single leaf ------------------------------------------------------------

def test_already_trained_leaf_costs_nothing():
    cat = skills({"id": 1})
    node = q({"kind": "skill", "skill_id": 1, "min_level": 3})
    assert character_gap(node, char(skill_levels={1: 3}), cat) == 0
    assert character_gap(node, char(skill_levels={1: 5}), cat) == 0


def test_untrained_leaf_costs_full_level():
    cat = skills({"id": 1})
    node = q({"kind": "skill", "skill_id": 1, "min_level": 3})
    assert character_gap(node, char(skill_levels={}), cat) == 8000


def test_partially_trained_leaf_costs_the_delta():
    cat = skills({"id": 1})
    node = q({"kind": "skill", "skill_id": 1, "min_level": 4})
    # 45255 (L4) - 1414 (L2)
    assert character_gap(node, char(skill_levels={1: 2}), cat) == 45255 - 1414


def test_leaf_cost_uses_skill_rank():
    cat = skills({"id": 1, "rank": 5})
    node = q({"kind": "skill", "skill_id": 1, "min_level": 2})
    assert character_gap(node, char(skill_levels={}), cat) == 1414 * 5


# --- prerequisite closure ---------------------------------------------------

def test_missing_prerequisite_is_counted():
    # skill 2 requires skill 1 @ 3; character has neither.
    cat = skills({"id": 1}, {"id": 2, "prereqs": [(1, 3)]})
    node = q({"kind": "skill", "skill_id": 2, "min_level": 1})
    # train skill 2 0->1 (250) + prereq skill 1 0->3 (8000)
    assert character_gap(node, char(skill_levels={}), cat) == 250 + 8000


def test_satisfied_prerequisite_is_not_counted():
    cat = skills({"id": 1}, {"id": 2, "prereqs": [(1, 3)]})
    node = q({"kind": "skill", "skill_id": 2, "min_level": 1})
    # prereq skill 1 already @5 >= 3, so only skill 2 0->1
    assert character_gap(node, char(skill_levels={1: 5}), cat) == 250


def test_recursive_prerequisite_closure():
    # 3 requires 2@1; 2 requires 1@2. Character has nothing.
    cat = skills(
        {"id": 1},
        {"id": 2, "prereqs": [(1, 2)]},
        {"id": 3, "prereqs": [(2, 1)]},
    )
    node = q({"kind": "skill", "skill_id": 3, "min_level": 1})
    # 3:0->1 (250) + 2:0->1 (250) + 1:0->2 (1414)
    assert character_gap(node, char(skill_levels={}), cat) == 250 + 250 + 1414


# --- AND merge --------------------------------------------------------------

def test_and_sums_independent_costs():
    cat = skills({"id": 1}, {"id": 2})
    node = q({"kind": "group", "op": "and", "children": [
        {"kind": "skill", "skill_id": 1, "min_level": 3},
        {"kind": "skill", "skill_id": 2, "min_level": 2},
    ]})
    assert character_gap(node, char(skill_levels={}), cat) == 8000 + 1414


def test_and_dedups_shared_prerequisite():
    # both 2 and 3 require 1@3; the shared prereq is paid once.
    cat = skills(
        {"id": 1},
        {"id": 2, "prereqs": [(1, 3)]},
        {"id": 3, "prereqs": [(1, 3)]},
    )
    node = q({"kind": "group", "op": "and", "children": [
        {"kind": "skill", "skill_id": 2, "min_level": 1},
        {"kind": "skill", "skill_id": 3, "min_level": 1},
    ]})
    # 2:250 + 3:250 + shared prereq 1:8000 (once)
    assert character_gap(node, char(skill_levels={}), cat) == 250 + 250 + 8000


def test_and_takes_max_level_per_skill():
    cat = skills({"id": 1})
    node = q({"kind": "group", "op": "and", "children": [
        {"kind": "skill", "skill_id": 1, "min_level": 2},
        {"kind": "skill", "skill_id": 1, "min_level": 4},
    ]})
    # only the higher requirement matters: L4 from 0
    assert character_gap(node, char(skill_levels={}), cat) == 45255


# --- OR cheapest branch -----------------------------------------------------

def test_or_picks_cheapest_branch_for_character():
    cat = skills({"id": 1}, {"id": 2})
    node = q({"kind": "group", "op": "or", "children": [
        {"kind": "skill", "skill_id": 1, "min_level": 5},
        {"kind": "skill", "skill_id": 2, "min_level": 1},
    ]})
    # branch 1: 4->5 = 256000-45255 = 210745; branch 2: 0->1 = 250. min = 250.
    c = char(skill_levels={1: 4})
    assert character_gap(node, c, cat) == 250


def test_or_is_zero_when_a_branch_already_matches():
    cat = skills({"id": 1}, {"id": 2})
    node = q({"kind": "group", "op": "or", "children": [
        {"kind": "skill", "skill_id": 1, "min_level": 5},
        {"kind": "skill", "skill_id": 2, "min_level": 5},
    ]})
    assert character_gap(node, char(skill_levels={1: 5}), cat) == 0


def test_nested_and_under_or():
    # (1>=4 AND 2>=3) OR 3>=1
    cat = skills({"id": 1}, {"id": 2}, {"id": 3})
    node = q({"kind": "group", "op": "or", "children": [
        {"kind": "group", "op": "and", "children": [
            {"kind": "skill", "skill_id": 1, "min_level": 4},
            {"kind": "skill", "skill_id": 2, "min_level": 3},
        ]},
        {"kind": "skill", "skill_id": 3, "min_level": 1},
    ]})
    # AND branch from scratch: 45255 + 8000 = 53255; single-skill branch: 250.
    assert character_gap(node, char(skill_levels={}), cat) == 250
