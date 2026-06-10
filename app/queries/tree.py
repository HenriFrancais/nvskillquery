"""Query expression tree: arbitrarily nested AND/OR groups over two leaf
condition kinds. The same JSON shape is produced by the frontend builder and
encoded into shareable URLs, so it is strictly validated here
(extra="forbid", bounded depth/size, references checked against the
snapshot)."""

from __future__ import annotations

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


class CharTypeCondition(BaseModel):
    kind: Literal["char_type"]
    char_type: str = Field(min_length=1)
    model_config = ConfigDict(extra="forbid")


class GroupNode(BaseModel):
    kind: Literal["group"]
    op: Literal["and", "or"]
    children: list[QueryNode] = Field(min_length=1)
    model_config = ConfigDict(extra="forbid")


QueryNode = Annotated[
    GroupNode | SkillCondition | CharTypeCondition, Field(discriminator="kind")
]

# Plain union for signatures (QueryNode itself is an Annotated form for pydantic).
AnyQueryNode = GroupNode | SkillCondition | CharTypeCondition

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
    """Reject references to skills/types the snapshot doesn't know, listing the
    offenders — better UX than silently matching nothing."""
    unknown_skills: list[int] = []
    unknown_types: list[str] = []
    type_set = set(snapshot.char_types)
    stack: list[AnyQueryNode] = [root]
    while stack:
        node = stack.pop()
        if isinstance(node, GroupNode):
            stack.extend(node.children)
        elif isinstance(node, SkillCondition):
            if node.skill_id not in snapshot.skills:
                unknown_skills.append(node.skill_id)
        elif node.char_type not in type_set:
            unknown_types.append(node.char_type)
    problems = []
    if unknown_skills:
        problems.append(f"unknown skill ids: {sorted(set(unknown_skills))}")
    if unknown_types:
        problems.append(f"unknown character types: {sorted(set(unknown_types))}")
    if problems:
        raise QueryValidationError("; ".join(problems))
