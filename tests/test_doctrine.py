"""Doctrine fit flattening, tier expansion, and ref codec — pure logic."""

from __future__ import annotations

import pytest

from app.queries.doctrine import (
    DoctrineError,
    DoctrineRef,
    build_doctrine_fits,
    decode_doctrine_ref,
    encode_doctrine_ref,
    expand_fit,
    find_fit,
    fit_skill_counts,
)
from app.queries.tree import GroupNode, SkillCondition
from app.sources.payloads import DoctrinesApiPayload
from tests.helpers import catalog_from

# Catalogue with skills 1..4 known; 999 is unknown.
CATALOG = catalog_from(
    [
        {"skill_id": 1, "name": "S1", "group_id": 10, "group_name": "G"},
        {"skill_id": 2, "name": "S2", "group_id": 10, "group_name": "G"},
        {"skill_id": 3, "name": "S3", "group_id": 10, "group_name": "G"},
        {"skill_id": 4, "name": "S4", "group_id": 10, "group_name": "G"},
    ]
)


def _payload(entries: list[dict]) -> DoctrinesApiPayload:
    return DoctrinesApiPayload.model_validate(entries)


FIT = {
    "doctrine": "BDA",
    "role": "Mainline",
    "ship_type": "Legion",
    "fit_name": "DPS",
    "fit_eft": "[Legion, ...]",  # ignored
    "defining_items": ["x"],  # ignored
    "skillpacks": {
        "Core": [
            {"skill_id": 1, "level_yellow": 4, "level_green": 5},
            {"skill_id": 2, "level_yellow": 0, "level_green": 3},  # green-only
        ],
        "Extra": [
            {"skill_id": 3, "level_yellow": 3, "level_green": 4},
        ],
    },
}


def test_flatten_collects_all_packs():
    fits = build_doctrine_fits(_payload([FIT]), CATALOG)
    assert len(fits) == 1
    fit = fits[0]
    assert (fit.doctrine, fit.role, fit.ship_type, fit.fit_name) == (
        "BDA",
        "Mainline",
        "Legion",
        "DPS",
    )
    assert {s.skill_id for s in fit.skills} == {1, 2, 3}


def test_unknown_skill_ids_dropped():
    entry = {
        **FIT,
        "skillpacks": {"Core": [{"skill_id": 999, "level_yellow": 4, "level_green": 5},
                                {"skill_id": 1, "level_yellow": 3, "level_green": 3}]},
    }
    fit = build_doctrine_fits(_payload([entry]), CATALOG)[0]
    assert {s.skill_id for s in fit.skills} == {1}


def test_duplicate_skill_across_packs_takes_max():
    entry = {
        **FIT,
        "skillpacks": {
            "A": [{"skill_id": 1, "level_yellow": 2, "level_green": 3}],
            "B": [{"skill_id": 1, "level_yellow": 4, "level_green": 5}],
        },
    }
    fit = build_doctrine_fits(_payload([entry]), CATALOG)[0]
    assert len(fit.skills) == 1
    assert (fit.skills[0].level_yellow, fit.skills[0].level_green) == (4, 5)


def test_fits_sorted_by_identity_tuple():
    a = {**FIT, "doctrine": "Zerg", "role": "A", "ship_type": "S", "fit_name": ""}
    b = {**FIT, "doctrine": "BDA", "role": "A", "ship_type": "S", "fit_name": ""}
    fits = build_doctrine_fits(_payload([a, b]), CATALOG)
    assert [f.doctrine for f in fits] == ["BDA", "Zerg"]


def test_expand_yellow_drops_zero_and_uses_yellow_level():
    fit = build_doctrine_fits(_payload([FIT]), CATALOG)[0]
    node = expand_fit(fit, "yellow")
    assert isinstance(node, GroupNode)
    assert node.op == "and"
    # skill 2 (yellow 0) dropped; 1@4 and 3@3 kept at the yellow level.
    by_id = {c.skill_id: c for c in node.children if isinstance(c, SkillCondition)}
    assert set(by_id) == {1, 3}
    assert by_id[1].min_level == 4
    assert by_id[3].min_level == 3


def test_expand_green_keeps_all_and_uses_green_level():
    fit = build_doctrine_fits(_payload([FIT]), CATALOG)[0]
    node = expand_fit(fit, "green")
    by_id = {c.skill_id: c.min_level for c in node.children if isinstance(c, SkillCondition)}
    assert by_id == {1: 5, 2: 3, 3: 4}


def test_expand_raises_when_no_skills_at_tier():
    entry = {
        **FIT,
        "skillpacks": {"Core": [{"skill_id": 1, "level_yellow": 0, "level_green": 4}]},
    }
    fit = build_doctrine_fits(_payload([entry]), CATALOG)[0]
    with pytest.raises(DoctrineError):
        expand_fit(fit, "yellow")


def test_fit_skill_counts():
    fit = build_doctrine_fits(_payload([FIT]), CATALOG)[0]
    # yellow: skills 1 and 3 (skill 2 is yellow 0). green: all three.
    assert fit_skill_counts(fit) == (2, 3)


def test_find_fit_matches_identity_tuple():
    fits = build_doctrine_fits(_payload([FIT]), CATALOG)

    class _Snap:
        doctrines = fits

    ref = DoctrineRef(
        doctrine="BDA", role="Mainline", ship_type="Legion", fit_name="DPS", tier="green"
    )
    assert find_fit(_Snap, ref) is fits[0]  # type: ignore[arg-type]
    miss = DoctrineRef(
        doctrine="BDA", role="Mainline", ship_type="Legion", fit_name="Nope", tier="green"
    )
    assert find_fit(_Snap, miss) is None  # type: ignore[arg-type]


def test_ref_codec_round_trip():
    ref = DoctrineRef(
        doctrine="STRAT", role="Logi", ship_type="Tengu", fit_name="Logi Tengu / X", tier="yellow"
    )
    assert decode_doctrine_ref(encode_doctrine_ref(ref)) == ref


def test_decode_bad_ref_raises():
    with pytest.raises(ValueError):
        decode_doctrine_ref("!!!not-base64!!!")


def test_build_snapshot_includes_doctrines():
    from tests.helpers import CATALOG_SKILLS, snapshot_from

    snap = snapshot_from(
        CATALOG_SKILLS,
        skills_entries=[],
        users_entries=[],
        doctrines_entries=[
            {
                "doctrine": "BDA",
                "role": "Mainline",
                "ship_type": "Legion",
                "fit_name": "DPS",
                "skillpacks": {
                    "Core": [{"skill_id": 1, "level_yellow": 4, "level_green": 5}],
                    # skill 999 isn't in CATALOG_SKILLS → dropped.
                    "X": [{"skill_id": 999, "level_yellow": 1, "level_green": 1}],
                },
            }
        ],
    )
    assert len(snap.doctrines) == 1
    assert {s.skill_id for s in snap.doctrines[0].skills} == {1}


def test_build_snapshot_no_doctrines_by_default():
    from tests.helpers import CATALOG_SKILLS, snapshot_from

    snap = snapshot_from(CATALOG_SKILLS, skills_entries=[], users_entries=[])
    assert snap.doctrines == ()
