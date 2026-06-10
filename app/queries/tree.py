"""Query expression tree: arbitrarily nested AND/OR groups over skill
conditions only. The same JSON shape is produced by the frontend builder and
encoded into shareable URLs, so it is strictly validated here
(extra="forbid", bounded depth/size, references checked against the
snapshot). Character groups are NOT query conditions — they arrive as a
separate pool filter and are validated by validate_groups."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.snapshot.models import Snapshot

MAX_DEPTH = 8
MAX_NODES = 100


class QueryValidationError(ValueError):
    """Structurally valid JSON that fails semantic limits or references."""


class SkillCondition(BaseModel):
    kind: Literal["skill"]
    skill_id: int
    # Matches characters with the skill trained at this level or higher.
    min_level: int = Field(ge=1, le=5)
    model_config = ConfigDict(extra="forbid")


class GroupNode(BaseModel):
    kind: Literal["group"]
    op: Literal["and", "or"]
    children: list[QueryNode] = Field(min_length=1)
    model_config = ConfigDict(extra="forbid")


QueryNode = Annotated[GroupNode | SkillCondition, Field(discriminator="kind")]

# Plain union for signatures (QueryNode itself is an Annotated form for pydantic).
AnyQueryNode = GroupNode | SkillCondition

GroupNode.model_rebuild()

QUERY_NODE_ADAPTER: TypeAdapter[AnyQueryNode] = TypeAdapter(QueryNode)


def validate_limits(root: AnyQueryNode) -> None:
    """Bound tree size and nesting depth (the tree arrives user-controlled
    from a URL parameter)."""
    nodes = 0
    stack: list[tuple[AnyQueryNode, int]] = [(root, 1)]
    while stack:
        node, depth = stack.pop()
        nodes += 1
        if depth > MAX_DEPTH:
            raise QueryValidationError(f"query exceeds maximum nesting depth of {MAX_DEPTH}")
        if nodes > MAX_NODES:
            raise QueryValidationError(f"query exceeds maximum size of {MAX_NODES} nodes")
        if isinstance(node, GroupNode):
            stack.extend((child, depth + 1) for child in node.children)


def validate_refs(root: AnyQueryNode, snapshot: Snapshot) -> None:
    """Reject references to skills the snapshot doesn't know, listing the
    offenders — better UX than silently matching nothing."""
    unknown_skills: list[int] = []
    stack: list[AnyQueryNode] = [root]
    while stack:
        node = stack.pop()
        if isinstance(node, GroupNode):
            stack.extend(node.children)
        elif node.skill_id not in snapshot.skills:
            unknown_skills.append(node.skill_id)
    if unknown_skills:
        raise QueryValidationError(f"unknown skill ids: {sorted(set(unknown_skills))}")


def validate_groups(groups: Sequence[str], snapshot: Snapshot) -> None:
    """Reject pool filters naming groups outside the snapshot vocabulary."""
    unknown = sorted(set(groups) - set(snapshot.character_groups))
    if unknown:
        raise QueryValidationError(f"unknown character groups: {unknown}")
