"""Tests for app/sde/catalog.py — loading the processed SDE artifact."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import Settings
from app.sde.catalog import SdeCatalog, SdeCatalogMissingError, load_sde_catalog

ARTIFACT = {
    "sde_build_number": 1234,
    "skills": [
        {
            "skill_id": 3300,
            "name": "Gunnery",
            "group_id": 255,
            "group_name": "Gunnery",
            "prerequisites": [],
        },
        {
            "skill_id": 3301,
            "name": "Small Hybrid Turret",
            "group_id": 255,
            "group_name": "Gunnery",
            "prerequisites": [{"skill_id": 3300, "level": 2}],
        },
    ],
}


def _settings(tmp_path: Path, **kw: object) -> Settings:
    return Settings(sde_dir=tmp_path / "sde", demo_data_dir=tmp_path / "demo", **kw)


def test_loads_artifact(tmp_path: Path) -> None:
    settings = _settings(tmp_path, data_source="real")
    settings.sde_dir.mkdir(parents=True)
    (settings.sde_dir / "skills.json").write_text(json.dumps(ARTIFACT))

    catalog = load_sde_catalog(settings)

    assert isinstance(catalog, SdeCatalog)
    assert catalog.build_number == 1234
    assert catalog.skills[3301].name == "Small Hybrid Turret"
    assert catalog.skills[3301].prerequisites[0].skill_id == 3300
    assert catalog.skills[3301].prerequisites[0].level == 2


def test_demo_falls_back_to_demo_catalogue(tmp_path: Path) -> None:
    settings = _settings(tmp_path, data_source="demo")
    settings.demo_data_dir.mkdir(parents=True)
    (settings.demo_data_dir / "sde_skills.json").write_text(json.dumps(ARTIFACT))

    catalog = load_sde_catalog(settings)

    assert catalog.build_number == 1234
    assert set(catalog.skills) == {3300, 3301}


def test_artifact_preferred_over_demo_fallback(tmp_path: Path) -> None:
    settings = _settings(tmp_path, data_source="demo")
    settings.sde_dir.mkdir(parents=True)
    settings.demo_data_dir.mkdir(parents=True)
    real = dict(ARTIFACT, sde_build_number=9999)
    (settings.sde_dir / "skills.json").write_text(json.dumps(real))
    (settings.demo_data_dir / "sde_skills.json").write_text(json.dumps(ARTIFACT))

    assert load_sde_catalog(settings).build_number == 9999


def test_real_mode_without_artifact_raises(tmp_path: Path) -> None:
    settings = _settings(tmp_path, data_source="real")

    with pytest.raises(SdeCatalogMissingError):
        load_sde_catalog(settings)
