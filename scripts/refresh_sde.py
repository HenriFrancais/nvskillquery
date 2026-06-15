"""Refresh the processed SDE skill catalogue (var/sde/skills.json).

Checks CCP's latest build number (a ~200 B fetch) and only downloads the
~80 MB jsonl zip when the cached artifact is stale. Nothing here is committed
to git; the Dockerfile runs this behind a BuildKit cache mount, and local dev
runs it directly:

    uv run python scripts/refresh_sde.py [--cache var/sde] [--out var/sde]

Cache layout (also the artifact layout when --out == --cache):

    manifest.json   {"buildNumber": <int>}
    skills.json     {"sde_build_number": <int>, "skills": [...]}

Exit codes: 0 = artifact current (refreshed or already fresh, or check failed
but a usable artifact exists); 1 = no artifact and refresh impossible.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

import httpx

MANIFEST_URL = "https://developers.eveonline.com/static-data/tranquility/latest.jsonl"
SDE_ZIP_URL = "https://developers.eveonline.com/static-data/eve-online-static-data-latest-jsonl.zip"

SKILL_CATEGORY_ID = 16
# typeDogma attribute pairs: (required skill type id, required level).
PREREQ_ATTRS = [(182, 277), (183, 278), (184, 279)]
# skillTimeConstant — the skill's rank / training-time multiplier.
RANK_ATTR = 275

NEEDED_FILES = ("types.jsonl", "groups.jsonl", "typeDogma.jsonl")


def parse_build_number(latest_jsonl_text: str) -> int:
    """Extract the current build number from latest.jsonl.

    Observed in the wild as a single JSON line with a top-level buildNumber;
    the docs also describe a _key-keyed record list with an "sde" record.
    Accept both.
    """
    for line in latest_jsonl_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            continue
        if record.get("_key") in (None, "sde") and "buildNumber" in record:
            return int(record["buildNumber"])
    raise ValueError("no buildNumber found in latest.jsonl")


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _en_name(record: dict) -> str:
    name = record.get("name")
    if isinstance(name, dict):
        return str(name.get("en") or next(iter(name.values()), ""))
    return str(name or "")


def process_sde_files(
    types_path: Path, groups_path: Path, dogma_path: Path, build_number: int
) -> dict:
    """Reduce the three SDE jsonl files to the app's compact skill catalogue."""
    skill_groups: dict[int, str] = {
        int(g["_key"]): _en_name(g)
        for g in _iter_jsonl(groups_path)
        if g.get("categoryID") == SKILL_CATEGORY_ID
    }

    skills: dict[int, dict] = {}
    for t in _iter_jsonl(types_path):
        group_id = t.get("groupID")
        if group_id not in skill_groups or not t.get("published"):
            continue
        type_id = int(t["_key"])
        skills[type_id] = {
            "skill_id": type_id,
            "name": _en_name(t),
            "group_id": int(group_id),
            "group_name": skill_groups[group_id],
            "prerequisites": [],
            "rank": 1,
        }

    for d in _iter_jsonl(dogma_path):
        type_id = int(d["_key"])
        if type_id not in skills:
            continue
        attrs = {
            int(a["attributeID"]): a["value"]
            for a in d.get("dogmaAttributes", [])
            if "attributeID" in a and "value" in a
        }
        # Skill rank (training-time multiplier), dogma attr 275. Absent for a
        # handful of skills — default to 1.
        if RANK_ATTR in attrs:
            skills[type_id]["rank"] = int(attrs[RANK_ATTR])
        prereqs = []
        for skill_attr, level_attr in PREREQ_ATTRS:
            if skill_attr in attrs and level_attr in attrs:
                target = int(attrs[skill_attr])
                level = int(attrs[level_attr])
                # Drop prereqs pointing outside the published skill set.
                if target in skills and 1 <= level <= 5:
                    prereqs.append({"skill_id": target, "level": level})
        skills[type_id]["prerequisites"] = prereqs

    return {
        "sde_build_number": build_number,
        "skills": [skills[k] for k in sorted(skills)],
    }


def _read_manifest(cache_dir: Path) -> dict:
    path = cache_dir / "manifest.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def needs_refresh(cache_dir: Path, remote_build: int, force: bool = False) -> bool:
    if force:
        # CCP can revise SDE data in place under an unchanged build number, so
        # the build-number comparison alone can serve stale data indefinitely
        # (the Docker cache mount then pins it across rebuilds). --force bypasses
        # the short-circuit and always re-downloads.
        return True
    local_build = int(_read_manifest(cache_dir).get("buildNumber") or 0)
    return remote_build != local_build or not (cache_dir / "skills.json").exists()


def _download_and_process(cache_dir: Path, remote_build: int, timeout: float) -> None:
    zip_path = cache_dir / "sde-latest.zip.partial"
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        with client.stream("GET", SDE_ZIP_URL) as resp:
            resp.raise_for_status()
            with zip_path.open("wb") as out:
                for chunk in resp.iter_bytes(chunk_size=64 * 1024):
                    out.write(chunk)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            available = set(zf.namelist())
            missing = [n for n in NEEDED_FILES if n not in available]
            if missing:
                raise RuntimeError(f"SDE zip missing expected files: {missing}")
            for name in NEEDED_FILES:
                with zf.open(name) as src, (cache_dir / name).open("wb") as dst:
                    shutil.copyfileobj(src, dst, 64 * 1024)
    finally:
        zip_path.unlink(missing_ok=True)

    artifact = process_sde_files(
        types_path=cache_dir / "types.jsonl",
        groups_path=cache_dir / "groups.jsonl",
        dogma_path=cache_dir / "typeDogma.jsonl",
        build_number=remote_build,
    )
    tmp = cache_dir / "skills.json.tmp"
    tmp.write_text(json.dumps(artifact, separators=(",", ":")))
    tmp.replace(cache_dir / "skills.json")
    (cache_dir / "manifest.json").write_text(json.dumps({"buildNumber": remote_build}))
    # The raw extracts are only needed during processing.
    for name in NEEDED_FILES:
        (cache_dir / name).unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path("var/sde"))
    parser.add_argument("--out", type=Path, default=None,
                        help="copy the artifact here after refresh (default: cache dir)")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument(
        "--force", action="store_true",
        help="re-download even when the build number is unchanged (catches "
             "in-place CCP SDE corrections; use in deploys to defeat a stale "
             "cache mount)",
    )
    args = parser.parse_args(argv)

    cache: Path = args.cache
    cache.mkdir(parents=True, exist_ok=True)
    have_artifact = (cache / "skills.json").exists()

    try:
        resp = httpx.get(MANIFEST_URL, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
        remote_build = parse_build_number(resp.text)
    except Exception as exc:  # noqa: BLE001 — any network/parse failure
        if have_artifact:
            print(f"WARNING: SDE version check failed ({exc}); using cached artifact",
                  file=sys.stderr)
            return _emit(cache, args.out)
        print(f"ERROR: SDE version check failed and no cached artifact exists: {exc}",
              file=sys.stderr)
        return 1

    if needs_refresh(cache, remote_build, force=args.force):
        why = "forced" if args.force else "stale or missing"
        print(f"SDE {why}; downloading build {remote_build}…", file=sys.stderr)
        try:
            _download_and_process(cache, remote_build, args.timeout)
        except Exception as exc:  # noqa: BLE001
            if have_artifact:
                print(f"WARNING: SDE refresh failed ({exc}); using cached artifact",
                      file=sys.stderr)
                return _emit(cache, args.out)
            print(f"ERROR: SDE refresh failed and no cached artifact exists: {exc}",
                  file=sys.stderr)
            return 1
        print(f"SDE artifact refreshed to build {remote_build}", file=sys.stderr)
    else:
        print(f"SDE artifact current (build {remote_build})", file=sys.stderr)
    return _emit(cache, args.out)


def _emit(cache: Path, out: Path | None) -> int:
    if out is not None and out.resolve() != cache.resolve():
        out.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cache / "skills.json", out / "skills.json")
        shutil.copy2(cache / "manifest.json", out / "manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
