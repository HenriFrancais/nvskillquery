"""Load the processed SDE skill catalogue produced by scripts/refresh_sde.py.

The artifact (var/sde/skills.json, never committed) is the authoritative
skill catalogue: the upstream skills API only contributes trained levels.
DATA_SOURCE=demo can run without an artifact via the small committed
fallback catalogue in data_demo/sde_skills.json, so offline dev works.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import Settings, get_settings
from app.observability.logging import log
from app.snapshot.models import SkillDef
from app.sources.payloads import SkillPrereq


class SdeCatalogMissingError(RuntimeError):
    """No processed SDE artifact and no applicable fallback."""


@dataclass(slots=True, frozen=True)
class SdeCatalog:
    build_number: int
    skills: dict[int, SkillDef]


def _parse(path: Path) -> SdeCatalog:
    data = json.loads(path.read_text())
    skills = {
        int(s["skill_id"]): SkillDef(
            skill_id=int(s["skill_id"]),
            name=s["name"],
            group_id=int(s["group_id"]),
            group_name=s["group_name"],
            rank=int(s.get("rank", 1)),
            prerequisites=tuple(
                SkillPrereq(skill_id=p["skill_id"], level=p["level"])
                for p in s.get("prerequisites", [])
            ),
        )
        for s in data["skills"]
    }
    return SdeCatalog(build_number=int(data["sde_build_number"]), skills=skills)


def load_sde_catalog(settings: Settings) -> SdeCatalog:
    artifact = settings.sde_dir / "skills.json"
    if artifact.exists():
        catalog = _parse(artifact)
        log.info("sde.catalog_loaded", source=str(artifact),
                 build_number=catalog.build_number, skills=len(catalog.skills))
        return catalog
    if settings.data_source == "demo":
        fallback = settings.demo_data_dir / "sde_skills.json"
        if fallback.exists():
            catalog = _parse(fallback)
            log.info("sde.catalog_loaded", source=str(fallback),
                     build_number=catalog.build_number, skills=len(catalog.skills))
            return catalog
    raise SdeCatalogMissingError(
        f"no SDE artifact at {artifact} — run `python scripts/refresh_sde.py` "
        "(or use DATA_SOURCE=demo with data_demo/sde_skills.json present)"
    )


@lru_cache(maxsize=1)
def get_sde_catalog() -> SdeCatalog:
    return load_sde_catalog(get_settings())


def reset_sde_catalog_for_tests() -> None:
    get_sde_catalog.cache_clear()
