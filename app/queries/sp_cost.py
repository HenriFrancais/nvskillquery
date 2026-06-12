"""Minimal additional skill points for a character to satisfy a query tree.

The skills API carries only trained levels, so "how far is this character from
matching" is derived: each query leaf expands to its prerequisite closure, an
AND merges children by max level (paying shared skills once), and an OR picks
the cheapest branch for that specific character. The result feeds the
distance-to-target chart. Pure functions — no snapshot or HTTP machinery.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.queries.tree import AnyQueryNode, GroupNode
from app.snapshot.models import CharacterRecord, SkillDef

# Cumulative SP to reach each level for a rank-1 skill, indexed by level 0..5.
# A skill of rank R costs R times these values.
SP_PER_LEVEL = (0, 250, 1414, 8000, 45255, 256000)


def skill_points(rank: int, level: int) -> int:
    """Cumulative SP to have a rank-`rank` skill trained to `level`."""
    return rank * SP_PER_LEVEL[level]


def _closure(skill_id: int, level: int, skills: Mapping[int, SkillDef]) -> dict[int, int]:
    """Required level per skill to have `skill_id` at `level`, including the
    recursive prerequisite chain (max level per skill across all paths)."""
    required: dict[int, int] = {}
    stack: list[tuple[int, int]] = [(skill_id, level)]
    while stack:
        sid, lvl = stack.pop()
        if lvl <= required.get(sid, 0):
            continue  # already required at this level or higher
        required[sid] = lvl
        sdef = skills.get(sid)
        if sdef is not None:
            for prereq in sdef.prerequisites:
                stack.append((prereq.skill_id, prereq.level))
    return required


def _required_levels(
    node: AnyQueryNode, char: CharacterRecord, skills: Mapping[int, SkillDef]
) -> dict[int, int]:
    """The skill -> level map this character must reach to satisfy `node`,
    resolving OR to the cheapest branch for this character."""
    if isinstance(node, GroupNode):
        if node.op == "and":
            merged: dict[int, int] = {}
            for child in node.children:
                for sid, lvl in _required_levels(child, char, skills).items():
                    if lvl > merged.get(sid, 0):
                        merged[sid] = lvl
            return merged
        # OR: the branch with the smallest cost for this character.
        best: dict[int, int] = {}
        best_cost = -1
        for child in node.children:
            req = _required_levels(child, char, skills)
            cost = _deficit_cost(req, char, skills)
            if best_cost < 0 or cost < best_cost:
                best_cost, best = cost, req
        return best
    return _closure(node.skill_id, node.min_level, skills)


def _deficit_cost(
    required: Mapping[int, int], char: CharacterRecord, skills: Mapping[int, SkillDef]
) -> int:
    """SP to lift this character from its current levels up to `required`."""
    total = 0
    for sid, lvl in required.items():
        current = char.skill_levels.get(sid, 0)
        if current < lvl:
            rank = skills[sid].rank if sid in skills else 1
            total += skill_points(rank, lvl) - skill_points(rank, current)
    return total


def character_gap(
    node: AnyQueryNode, char: CharacterRecord, skills: Mapping[int, SkillDef]
) -> int:
    """Minimal additional SP for `char` to satisfy `node`. Zero when the
    character already matches."""
    return _deficit_cost(_required_levels(node, char, skills), char, skills)
