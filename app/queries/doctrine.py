"""Doctrine fits → skill queries.

A doctrine fit (from the NV doctrine_definitions API) bundles ~50 skill
requirements as a yellow/green traffic-light pair per skill. Selecting a fit +
tier flattens it into the ordinary AND query the rest of the pipeline already
understands, so evaluate/aggregate stay untouched — the doctrine is just an
alternative *source* of the skill set.

This module is pure (no I/O): the flatten/filter runs at snapshot-build time,
the expand runs per request.
"""

from __future__ import annotations

import base64
import binascii
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.observability.logging import log
from app.queries.tree import MAX_NODES, AnyQueryNode, GroupNode, SkillCondition
from app.sde.catalog import SdeCatalog
from app.snapshot.models import DoctrineFit, DoctrineSkillReq, Snapshot
from app.sources.payloads import DoctrinesApiPayload

Tier = Literal["yellow", "green"]


class DoctrineError(ValueError):
    """A doctrine ref can't be turned into a runnable query (unknown fit, or
    no skills required at the chosen tier)."""


class DoctrineRefDecodeError(ValueError):
    """The d= parameter is not a valid encoded doctrine ref."""


class DoctrineRef(BaseModel):
    """Identifies a fit + tier — the compact, stable form carried in share
    links and POST bodies instead of the 50-skill expansion."""

    doctrine: str
    role: str
    ship_type: str
    fit_name: str = ""
    tier: Tier


class DoctrineLabel(DoctrineRef):
    """A resolved ref: the identity + how many skills the expansion produced.
    Carried in the query response so the results header can name the doctrine."""

    skill_count: int


def build_doctrine_fits(
    payload: DoctrinesApiPayload, catalog: SdeCatalog
) -> tuple[DoctrineFit, ...]:
    """Flatten each fit's skillpacks into one deduped, catalogue-filtered skill
    list. Skills unknown to the SDE catalogue are dropped (logged once) so an
    expanded query never trips validate_refs; duplicates across packs take the
    max level. Fits are sorted by their identity tuple."""
    unknown: set[int] = set()
    fits: list[DoctrineFit] = []
    for entry in payload.root:
        merged: dict[int, DoctrineSkillReq] = {}
        for skills in entry.skillpacks.values():
            for s in skills:
                if s.skill_id not in catalog.skills:
                    if s.skill_id not in unknown:
                        unknown.add(s.skill_id)
                        log.warning("doctrine.unknown_skill", skill_id=s.skill_id)
                    continue
                prev = merged.get(s.skill_id)
                if prev is None:
                    merged[s.skill_id] = DoctrineSkillReq(
                        skill_id=s.skill_id,
                        level_yellow=s.level_yellow,
                        level_green=s.level_green,
                    )
                else:
                    merged[s.skill_id] = DoctrineSkillReq(
                        skill_id=s.skill_id,
                        level_yellow=max(prev.level_yellow, s.level_yellow),
                        level_green=max(prev.level_green, s.level_green),
                    )
        fits.append(
            DoctrineFit(
                doctrine=entry.doctrine,
                role=entry.role,
                ship_type=entry.ship_type,
                fit_name=entry.fit_name,
                skills=tuple(sorted(merged.values(), key=lambda r: r.skill_id)),
            )
        )
    fits.sort(key=lambda f: (f.doctrine, f.role, f.ship_type, f.fit_name))
    return tuple(fits)


def _tier_level(req: DoctrineSkillReq, tier: Tier) -> int:
    return req.level_yellow if tier == "yellow" else req.level_green


def fit_skill_counts(fit: DoctrineFit) -> tuple[int, int]:
    """(yellow_count, green_count) — how many skills are actually required at
    each tier (a tier level of 0 means "not required at this tier")."""
    yellow = sum(1 for s in fit.skills if s.level_yellow > 0)
    green = sum(1 for s in fit.skills if s.level_green > 0)
    return yellow, green


def expand_fit(fit: DoctrineFit, tier: Tier) -> GroupNode:
    """Build the AND query for this fit at the given tier. Skills whose tier
    level is 0 are dropped (not required at that tier)."""
    children: list[AnyQueryNode] = [
        SkillCondition(kind="skill", skill_id=s.skill_id, min_level=level)
        for s in fit.skills
        if (level := _tier_level(s, tier)) > 0
    ]
    if not children:
        raise DoctrineError(
            f"fit {fit.doctrine}/{fit.role}/{fit.ship_type}/{fit.fit_name} "
            f"has no skills required at the {tier} tier"
        )
    if len(children) >= MAX_NODES:
        # validate_limits would reject this downstream; warn so a fit that
        # outgrows the query-size cap is visible rather than a cryptic 422.
        log.warning(
            "doctrine.fit_exceeds_node_cap",
            doctrine=fit.doctrine,
            ship_type=fit.ship_type,
            skills=len(children),
            cap=MAX_NODES,
        )
    return GroupNode(kind="group", op="and", children=children)


def find_fit(snapshot: Snapshot, ref: DoctrineRef) -> DoctrineFit | None:
    """The fit matching the ref's identity tuple, or None."""
    for fit in snapshot.doctrines:
        if (fit.doctrine, fit.role, fit.ship_type, fit.fit_name) == (
            ref.doctrine,
            ref.role,
            ref.ship_type,
            ref.fit_name,
        ):
            return fit
    return None


def encode_doctrine_ref(ref: DoctrineRef) -> str:
    raw = ref.model_dump_json().encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_doctrine_ref(d: str) -> DoctrineRef:
    padded = d + "=" * (-len(d) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise DoctrineRefDecodeError("not valid base64url") from exc
    try:
        return DoctrineRef.model_validate_json(raw)
    except ValidationError as exc:
        raise DoctrineRefDecodeError(f"not a valid doctrine ref: {exc}") from exc
