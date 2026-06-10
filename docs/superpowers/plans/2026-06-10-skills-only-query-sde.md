# Skills-only queries, group pool filter, SDE catalogue, containerization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the query tree skills-only with a separate character-group pool filter, source the skill catalogue from the EVE SDE (refreshed at container build), and containerize the app following the router conventions.

**Architecture:** The snapshot keeps being the single in-memory data layer, but its skill catalogue now comes from a build-time-processed SDE artifact (`var/sde/skills.json`, gitignored) instead of the upstream skills API, which shrinks to trained levels. `run_query` gains a `groups` pool parameter that scopes evaluation and all counts. The frontend drops the char-type condition and gains a pool-chip row; share URLs carry `&g=`. A three-stage Dockerfile (frontend build, SDE refresh behind a BuildKit cache mount, uv runtime) plus compose bind to loopback per the NV Tools topology.

**Tech Stack:** FastAPI + pydantic v2, httpx, pytest; React + Vite + vitest; Docker BuildKit, uv.

**Spec:** `docs/superpowers/specs/2026-06-10-skills-only-query-sde-design.md`

---

## File map

| File | Action | Responsibility |
|---|---|---|
| `scripts/refresh_sde.py` | create | Build-number check, zip download, jsonl → `var/sde/skills.json` |
| `tests/test_refresh_sde.py` | create | Processor unit tests against fixture jsonl |
| `tests/fixtures/sde/*.jsonl` | create | Tiny types/groups/typeDogma fixtures |
| `app/sde/__init__.py`, `app/sde/catalog.py` | create | Load processed artifact (or demo fallback) into `SkillDef`s |
| `app/snapshot/models.py` | modify | `CharacterRecord.group`, `Snapshot.character_groups`, `Snapshot.sde_build_number` |
| `app/sources/payloads.py` | modify | Users payload renames; skills payload loses catalogue array |
| `app/snapshot/build.py` | modify | Take `SdeCatalog`; drop unknown trained skills |
| `app/snapshot/store.py` | modify | Pass catalogue into build |
| `app/queries/tree.py` | modify | Delete `CharTypeCondition`; add `validate_groups` |
| `app/queries/evaluate.py` | modify | Skill-only evaluation |
| `app/queries/aggregate.py` | modify | Pool semantics; `group` renames |
| `app/queries/csv_export.py` | modify | Column renames |
| `app/api/query.py` | modify | `groups` in body + `g=` on CSV; cache key |
| `app/api/catalog.py` | modify | `character_groups`, `sde_build_number` |
| `app/config.py` | modify | `sde_dir` setting |
| `scripts/gen_demo_fixtures.py` | modify | Home/Strat/Farm/Alpha; split catalogue into `data_demo/sde_skills.json` |
| `data_demo/*.json` | regenerate | New shapes |
| `docs/upstream-api.md` | modify | Contract update |
| `frontend/src/query/{model,builder,reducer,describe,encode}.ts` + tests | modify | char_type removal; groups URL param helpers |
| `frontend/src/api.ts` | modify | Renames + `groups` |
| `frontend/src/components/QueryBuilder/{CharTypePicker,GroupEditor}.tsx` | delete / modify | Drop type conditions |
| `frontend/src/components/PoolFilter.tsx` (+ test) | create | Group chips |
| `frontend/src/views/SkillQuery.tsx` | modify | Wire pool filter, `g=` param |
| `frontend/src/styles/app.css` | modify | Pool chip styles |
| `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `uv.lock`, `.gitignore` | create/modify | Containerization |

Tests-first throughout; one commit per task.

---

### Task 1: SDE refresh script + processor tests

**Files:**
- Create: `scripts/refresh_sde.py`
- Create: `tests/test_refresh_sde.py`, `tests/fixtures/sde/{types,groups,typeDogma}.jsonl`

- [ ] **Step 1.1: Write fixtures.** `tests/fixtures/sde/groups.jsonl` (two skill groups in category 16, one non-skill group):

```jsonl
{"_key": 255, "categoryID": 16, "name": {"en": "Gunnery"}, "published": true}
{"_key": 266, "categoryID": 16, "name": {"en": "Engineering"}, "published": true}
{"_key": 18, "categoryID": 4, "name": {"en": "Mineral"}, "published": true}
```

`types.jsonl` (two published skills, one unpublished skill, one non-skill type):

```jsonl
{"_key": 3300, "groupID": 255, "name": {"en": "Gunnery"}, "published": true}
{"_key": 3301, "groupID": 255, "name": {"en": "Small Hybrid Turret"}, "published": true}
{"_key": 3302, "groupID": 266, "name": {"en": "Secret Skill"}, "published": false}
{"_key": 34, "groupID": 18, "name": {"en": "Tritanium"}, "published": true}
```

`typeDogma.jsonl` (3301 requires 3300 @ 2; one prereq points at unpublished 3302 and must be dropped):

```jsonl
{"_key": 3301, "dogmaAttributes": [{"attributeID": 182, "value": 3300.0}, {"attributeID": 277, "value": 2.0}, {"attributeID": 183, "value": 3302.0}, {"attributeID": 278, "value": 4.0}]}
```

- [ ] **Step 1.2: Write failing tests** (`tests/test_refresh_sde.py`): `process_sde_files(types_path, groups_path, dogma_path, build_number)` returns the artifact dict; assert: only 3300+3301 present (category-16 + published only), group names resolved, 3301 prereq == `[{"skill_id": 3300, "level": 2}]` (3302 dropped), `sde_build_number` echoed. Also test `parse_build_number(latest_jsonl_text)` on a sample line `{"_key": "sde", "buildNumber": 27123456, ...}` and the short-circuit: `needs_refresh(cache_dir)` False when manifest matches.

- [ ] **Step 1.3: Run tests, verify fail** (`uv run pytest tests/test_refresh_sde.py -q` → import error).

- [ ] **Step 1.4: Implement `scripts/refresh_sde.py`.** Pure functions `parse_build_number`, `process_sde_files`, plus IO orchestration:

```python
"""Refresh the processed SDE skill catalogue (var/sde/skills.json).

Checks CCP's latest build number (a ~200B fetch) and only downloads the
~80MB jsonl zip when the cached artifact is stale. Nothing here is
committed to git; the Dockerfile runs this behind a BuildKit cache mount.

    uv run python scripts/refresh_sde.py [--cache var/sde] [--out var/sde]
"""
MANIFEST_URL = "https://developers.eveonline.com/static-data/tranquility/latest.jsonl"
SDE_ZIP_URL = "https://developers.eveonline.com/static-data/eve-online-static-data-latest-jsonl.zip"
SKILL_CATEGORY_ID = 16
PREREQ_ATTRS = [(182, 277), (183, 278), (184, 279)]
# parse_build_number: find the jsonl line whose _key == "sde", return ["buildNumber"]
# process_sde_files: groups = {_key: name.en} where categoryID==16;
#   skills = published types whose groupID in groups;
#   prereqs from typeDogma PREREQ_ATTRS pairs, dropping targets not in skills;
#   returns {"sde_build_number": n, "skills": [...]} sorted by skill_id
# main(): read cached manifest; fetch latest (on failure: warn+exit 0 if artifact exists, exit 1 otherwise);
#   if equal and skills.json exists -> exit 0; else download zip to cache, extract the 3 files,
#   process, write skills.json + manifest.json atomically (tmp+rename)
```

(Write the real code, mirroring `~/dev/router/app/sde/fetch.py` for the download/manifest mechanics; httpx with `follow_redirects=True`, 120 s timeout for the zip.)

- [ ] **Step 1.5: Tests pass**; `.gitignore` gains `var/`. **Commit** `feat: SDE refresh script (build-number check + jsonl -> skills.json)`.

### Task 2: SDE catalogue loader

**Files:**
- Create: `app/sde/__init__.py`, `app/sde/catalog.py`
- Modify: `app/config.py` (add `sde_dir: Path = Path("./var/sde")`)
- Test: `tests/test_sde_catalog.py`

- [ ] **Step 2.1: Failing tests:** loading a valid `skills.json` from tmp dir yields `SdeCatalog(build_number, skills: dict[int, SkillDef])` with prereqs as `SkillPrereq`; missing artifact + `data_source="demo"` falls back to `demo_data_dir/sde_skills.json`; missing artifact + `data_source="real"` raises `SdeCatalogMissingError`.

- [ ] **Step 2.2: Implement** `app/sde/catalog.py`:

```python
@dataclass(slots=True, frozen=True)
class SdeCatalog:
    build_number: int
    skills: dict[int, SkillDef]

def load_sde_catalog(settings: Settings) -> SdeCatalog: ...  # artifact -> fallback -> raise
@lru_cache(maxsize=1) get_sde_catalog() + reset_sde_catalog_for_tests()
```

`SkillDef` reused from `app/snapshot/models.py`. Loader resolves `group_name` straight from the artifact (it's denormalized there).

- [ ] **Step 2.3: Tests pass. Commit** `feat: SDE catalogue loader with demo fallback`.

### Task 3: Domain — group rename, skills-only tree, pool-filtered aggregation

**Files:**
- Modify: `app/snapshot/models.py`, `app/sources/payloads.py`, `app/snapshot/build.py`, `app/snapshot/store.py`, `app/queries/tree.py`, `app/queries/evaluate.py`, `app/queries/aggregate.py`, `app/queries/csv_export.py`
- Test: `tests/test_evaluate.py`, `tests/test_aggregate.py`, `tests/test_query_validation.py`, `tests/helpers.py`

- [ ] **Step 3.1: Update test helpers + write failing tests.** `tests/helpers.py` snapshot builders rename `character_type=` → `group=` and gain a pool of Home/Strat/Farm/Alpha; `build_snapshot` calls pass a stub `SdeCatalog`. New aggregate tests (exact behaviors from the spec):
  - `test_pool_scopes_matching_and_counts`: user with Home char (matches) + Farm char (matches); `groups=["Home"]` → `match_count == 1`, `total_characters == 1`, chips exclude the Farm char.
  - `test_zero_pool_user_dropped` / `test_zero_pool_user_included_when_non_matching`: user with only Farm chars, `groups=["Home"]` → absent; with `include_non_matching=True` → present as 0/0.
  - `test_main_outside_pool_shown_not_matching`: main is Farm, alt Home matches → row's `main_character.matches is False`, name still present.
  - `test_totals_are_pool_relative`: totals count only pool characters/users-with-pool-chars.
  - `test_empty_groups_means_all`.
  - tree tests: `char_type` payload now fails decode/validation; `validate_groups(["Nope"], snapshot)` raises listing the name.

- [ ] **Step 3.2: Verify failures.**

- [ ] **Step 3.3: Implement.**
  - `models.py`: `CharacterRecord.group: str`; `Snapshot.character_groups: tuple[str, ...]`; `Snapshot.sde_build_number: int`.
  - `payloads.py`: `UsersCharacterIn.group`, `UsersApiPayload.character_groups`; delete `SkillDefIn` and `SkillsApiPayload.skills` (keep `SkillPrereq` — now used by the SDE loader).
  - `build.py`: signature `build_snapshot(skills_payload, users_payload, catalog: SdeCatalog, version, fetched_at)`; `skills=catalog.skills`; drop trained entries whose id not in catalogue with one `log.warning("snapshot.unknown_skill", skill_id=...)` per id; vocabulary from `users_payload.character_groups` else distinct seen.
  - `store.py`: fetch catalogue via `get_sde_catalog()` and pass through.
  - `tree.py`: delete `CharTypeCondition`; `QueryNode = Annotated[GroupNode | SkillCondition, ...]`; `validate_refs` keeps only the skill branch; add:

```python
def validate_groups(groups: Sequence[str], snapshot: Snapshot) -> None:
    unknown = sorted(set(groups) - set(snapshot.character_groups))
    if unknown:
        raise QueryValidationError(f"unknown character groups: {unknown}")
```

  - `evaluate.py`: drop the char_type return (function ends at the skill branch).
  - `aggregate.py`: `run_query(snapshot, root, groups: Sequence[str] = (), include_non_matching=False)`; `pool = set(groups)`; per user `chars = [c for c in ... if not pool or c.group in pool]`; main looked up via `snapshot.characters[user.main_character_id]` (no longer necessarily in `chars`); `CharacterOut.group`; totals computed over pool members only (`total_users` = users with ≥1 pool char, `total_characters` = pool size).
  - `csv_export.py`: columns `main_character_group`, chips `f"{c.name} ({c.group})"`.

- [ ] **Step 3.4: Full backend tests pass** (`uv run pytest -q`; fix the integration/encode/fixture tests' compile errors as part of this step ONLY where they reference renamed fields — semantic API changes come in Task 4). **Commit** `feat: skills-only tree, group rename, pool-filtered aggregation`.

### Task 4: API layer — groups in request, g= on CSV, catalog response

**Files:**
- Modify: `app/api/query.py`, `app/api/catalog.py`
- Test: `tests/test_api_integration.py`

- [ ] **Step 4.1: Failing tests:** POST body `{"query": ..., "groups": ["Home"]}` scopes results; `groups: ["Nope"]` → 422; old `char_type` node in body → 422; CSV `?q=...&g=Home,Strat` scopes; catalog response has `character_groups` and `sde_build_number`, no `char_types`.

- [ ] **Step 4.2: Implement.**
  - `QueryRequest.groups: list[str] = []`; `_execute(snapshot, root, groups, include_non_matching)` calls `validate_groups`; cache key `f"{canonical_hash(root)}:{','.join(sorted(groups))}:{snapshot.version}:{include_non_matching}"`.
  - `export_csv(q: str, g: str = "", include_non_matching: bool = False)` → `groups = [s for s in g.split(",") if s]`.
  - `catalog.py`: rename field, add `sde_build_number=snapshot.sde_build_number`.

- [ ] **Step 4.3: Backend green. Commit** `feat: pool groups in query API + catalog renames`.

### Task 5: Demo fixtures + upstream contract doc

**Files:**
- Modify: `scripts/gen_demo_fixtures.py`, `docs/upstream-api.md`
- Regenerate: `data_demo/users_api.json`, `data_demo/skills_api.json`, create `data_demo/sde_skills.json`
- Test: `tests/test_fixtures.py`

- [ ] **Step 5.1:** Generator changes: `CHARACTER_GROUPS = ["Home", "Strat", "Farm", "Alpha"]` (weights e.g. mains mostly Home; alts spread Strat/Farm/Alpha); per-character key `"group"`; payload key `"character_groups"`; the fake skill catalogue (same 10×8 skills) now written to `data_demo/sde_skills.json` in the SDE-artifact shape (`{"sde_build_number": 0, "skills": [...]}`); `skills_api.json` keeps `generated_at` + `users` only.
- [ ] **Step 5.2:** Regenerate (`uv run python scripts/gen_demo_fixtures.py`), update `tests/test_fixtures.py` expectations, full suite green.
- [ ] **Step 5.3:** Rewrite `docs/upstream-api.md`: skills API = trained levels only; users API uses `group`/`character_groups` with Home/Strat/Farm/Alpha as the example vocabulary; note the SDE as catalogue source. **Commit** `feat: demo fixtures with character groups + SDE-shaped demo catalogue`.

### Task 6: Frontend — model/state, pool filter, view

**Files:**
- Modify: `frontend/src/query/{model,builder,reducer,describe,encode}.ts` and their `.test.ts`
- Modify: `frontend/src/api.ts`, `frontend/src/components/QueryBuilder/GroupEditor.tsx` (+ test), `frontend/src/views/SkillQuery.tsx`, `frontend/src/styles/app.css`
- Delete: `frontend/src/components/QueryBuilder/CharTypePicker.tsx`
- Create: `frontend/src/components/PoolFilter.tsx`, `frontend/src/components/PoolFilter.test.tsx`
- Create: `frontend/src/query/groups.ts` (g= param encode/parse) + test in `encode.test.ts`

- [ ] **Step 6.1: Failing tests first:** encode rejects `char_type` nodes; reducer has no `char_type` add; describe renders skills-only; `groupsToParam(["Home","Strat"], all)` omits param when all selected and `parseGroupsParam("Home,Strat", all)` filters unknown names; PoolFilter renders a chip per group, toggles selection, reports all-deselected.
- [ ] **Step 6.2: Implement.**
  - `model.ts`: delete `CharTypeCondition`; `QueryNode = GroupNode | SkillCondition`.
  - `builder.ts`/`reducer.ts`: delete `BuilderCharType`, the `char_type` branches and `add_condition` kind parameter (skill is the only condition).
  - `encode.ts`: `isQueryNode` drops the `char_type` case.
  - `describe.ts`: drop `type =` branch.
  - `api.ts`: `CharacterOut.group`, `CatalogResponse.character_groups` + `sde_build_number`; `api.query(query, groups, includeNonMatching)`; `exportCsvUrl(encoded, groups, includeNonMatching)` appends `&g=` when not-all.
  - `PoolFilter.tsx`: checkbox-chip row (`.pool-filter`, `.pool-chip`, `.pool-chip.on` styles); props `{groups: string[], selected: Set<string>, onToggle(name)}`.
  - `GroupEditor.tsx`: remove `+ type` button and CharTypePicker import/branch.
  - `SkillQuery.tsx`: `selectedGroups` state (default = all once catalog loads); init from `?g=`; Run disabled when `selectedGroups.size === 0`; pass groups to `api.query`/CSV/share URL (`&g=` omitted when all selected); results header shows the pool.
- [ ] **Step 6.3:** `npx tsc --noEmit && npx vitest run && npm run build` green. **Commit** `feat: frontend pool filter, skills-only builder`.

### Task 7: Containerization

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `docker-compose.yml`
- Create: `uv.lock` (`uv lock` from pyproject)
- Modify: `.gitignore` (ensure `var/`), `app/config.py` already has `sde_dir`

- [ ] **Step 7.1:** `Dockerfile` (modeled on `~/dev/router/Dockerfile`): stage `frontend-build` (node:20-alpine, `ARG VITE_URL_PREFIX`); stage `sde` (uv image, `COPY scripts/refresh_sde.py`, `RUN --mount=type=cache,target=/sde-cache python scripts/refresh_sde.py --cache /sde-cache --out /out/sde`); stage `runtime` (uv sync --frozen --no-dev, app code, `COPY --from=sde /out/sde ./var/sde`, `COPY --from=frontend-build /build/dist ./frontend/dist`, non-root `appuser`, `EXPOSE 8083`, uvicorn CMD `--port ${PORT:-8083}`).
- [ ] **Step 7.2:** `docker-compose.yml`: service `nvskills`, `ports: ["127.0.0.1:8083:8083"]`, env passthrough (`NV_TOKEN`, `URL_PREFIX`, `DATA_SOURCE`, `SKILLS_API_URL/TOKEN`, `USERS_API_URL/TOKEN`); `.dockerignore`: `.git node_modules .venv var frontend/dist .pytest_cache`.
- [ ] **Step 7.3:** `docker compose build && docker compose run --rm` smoke: `/healthz` 200, no-bearer 401, authed demo query 200. **Commit** `feat: containerize (Dockerfile with SDE build stage, compose)`.

### Task 8: End-to-end verification + dev launch

- [ ] **Step 8.1:** Full suites fresh: `uv run pytest -q`, `npx tsc --noEmit`, `npx vitest run`, `npm run build`.
- [ ] **Step 8.2:** Run `scripts/refresh_sde.py` once against the real CCP service into `var/sde/` and boot `DATA_SOURCE=demo` — confirms the real artifact loads (demo users trained-skill ids won't exist in the real SDE; demo mode keeps using the demo fallback unless `var/sde` exists, so do this check with a throwaway env `SDE_DIR=/tmp/sde-real` instead).
- [ ] **Step 8.3:** Headless-Chromium drive of the dev stack: pool chips render with Home/Strat/Farm/Alpha, deselect → Run disables, skills-only builder, run, share URL with `&g=`, CSV link. Screenshots.
- [ ] **Step 8.4:** Leave backend (8082) + Vite (5173) running for the user. **Commit** any fixes; final summary.
