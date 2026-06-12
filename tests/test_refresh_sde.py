"""Unit tests for the SDE processor (scripts/refresh_sde.py) against tiny
fixture jsonl files. No network."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from refresh_sde import (  # noqa: E402
    needs_refresh,
    parse_build_number,
    process_sde_files,
)

FIXTURES = Path(__file__).parent / "fixtures" / "sde"


def _process(build: int = 1234) -> dict:
    return process_sde_files(
        types_path=FIXTURES / "types.jsonl",
        groups_path=FIXTURES / "groups.jsonl",
        dogma_path=FIXTURES / "typeDogma.jsonl",
        build_number=build,
    )


def test_only_published_category16_skills() -> None:
    artifact = _process()
    ids = [s["skill_id"] for s in artifact["skills"]]
    # 3302 is unpublished, 34 is not in a skill group.
    assert ids == [3300, 3301]


def test_group_names_resolved() -> None:
    by_id = {s["skill_id"]: s for s in _process()["skills"]}
    assert by_id[3300]["group_id"] == 255
    assert by_id[3300]["group_name"] == "Gunnery"
    assert by_id[3301]["name"] == "Small Hybrid Turret"


def test_prerequisites_extracted_and_unknown_targets_dropped() -> None:
    by_id = {s["skill_id"]: s for s in _process()["skills"]}
    # 3301 requires 3300 @ 2; its second prereq targets unpublished 3302 → dropped.
    assert by_id[3301]["prerequisites"] == [{"skill_id": 3300, "level": 2}]
    assert by_id[3300]["prerequisites"] == []


def test_rank_extracted_and_defaults_to_one() -> None:
    by_id = {s["skill_id"]: s for s in _process()["skills"]}
    # 3301 carries dogma attr 275 (skillTimeConstant) = 6.
    assert by_id[3301]["rank"] == 6
    # 3300 has no dogma entry at all → rank defaults to 1.
    assert by_id[3300]["rank"] == 1


def test_build_number_echoed() -> None:
    assert _process(build=999)["sde_build_number"] == 999


def test_parse_build_number_single_object() -> None:
    # Router-observed shape: latest.jsonl is one JSON line with buildNumber.
    assert parse_build_number('{"buildNumber": 27123456, "releaseDate": "2026-06-01"}') == 27123456


def test_parse_build_number_keyed_records() -> None:
    text = '{"_key": "other", "x": 1}\n{"_key": "sde", "buildNumber": 27123457}'
    assert parse_build_number(text) == 27123457


def test_needs_refresh_short_circuits_when_current(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text(json.dumps({"buildNumber": 42}))
    (tmp_path / "skills.json").write_text(json.dumps({"sde_build_number": 42, "skills": []}))
    assert needs_refresh(tmp_path, remote_build=42) is False
    assert needs_refresh(tmp_path, remote_build=43) is True


def test_needs_refresh_when_artifact_missing(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text(json.dumps({"buildNumber": 42}))
    assert needs_refresh(tmp_path, remote_build=42) is True
