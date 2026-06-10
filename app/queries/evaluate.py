"""Query tree evaluation against a single character. Pure functions."""

from __future__ import annotations

from app.queries.tree import AnyQueryNode, GroupNode, SkillCondition
from app.snapshot.models import CharacterRecord


def character_matches(node: AnyQueryNode, char: CharacterRecord) -> bool:
    if isinstance(node, GroupNode):
        if node.op == "and":
            return all(character_matches(child, char) for child in node.children)
        return any(character_matches(child, char) for child in node.children)
    if isinstance(node, SkillCondition):
        return char.skill_levels.get(node.skill_id, 0) >= node.min_level
    return char.character_type == node.char_type
