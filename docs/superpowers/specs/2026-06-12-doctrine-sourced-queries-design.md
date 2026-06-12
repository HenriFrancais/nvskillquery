# Doctrine-sourced skill queries — design

## Goal

Let a privileged user query NV members against the full skill set required by a
specific **doctrine fit** (from the new NV `doctrine_definitions` API), choosing a
**yellow** or **green** tier requirement — as an alternative *source* for the skill
query alongside the existing manual builder. Both input modes feed the same
evaluation/aggregation pipeline (strict pass/fail per character).

## Upstream data (verified against the live API, 70 entries)

`GET /api/doctrine_definitions` → array of fits. Each fit:

- Identified by the tuple `(doctrine, role, ship_type, fit_name)` — **unique** across
  all 70 entries. `fit_name` may be empty (3 entries).
- `skillpacks`: `{ pack_name: [{skill_id, level_yellow, level_green}, …] }`. ~13 packs
  / ~53 skills per fit (range 21–77).
- Also carries `fit_eft`, `defining_items` (ignored by this feature).

Level semantics (confirmed from the data):

- `level_green` is always ≥ `level_yellow`; `level_green` is never 0.
- `level_yellow == 0` for 220 skill rows → that skill is **not required at the yellow
  tier** (green-only). No skill_id appears in two packs within one fit (if it ever does,
  take the **max** level defensively).

## Flatten + tier rule (the core transform)

Selecting a fit + tier produces a flat AND query:

- Flatten all skillpacks of the fit into one skill→{yellow,green} map (dedupe by max).
- For the chosen tier, `min_level = level_<tier>`; **drop any skill whose tier level is
  0**. Yellow drops the 220 green-only rows; green keeps everything (green ≥ 1 always).
- Emit an `and` `GroupNode` of `SkillCondition(skill_id, min_level)` — the existing query
  shape. Max fit = 77 skills → 78 nodes, under `MAX_NODES=100` (≈22 headroom; assert/log
  if upstream ever exceeds it). `evaluate.py` / `aggregate.py` are unchanged.

## Backend

Doctrine catalogue is folded into the existing **Snapshot** (shares caching, refresh,
`snapshot_version` with users/skills):

- `app/sources/payloads.py`: `DoctrineSkillIn{skill_id, level_yellow(0–5), level_green(0–5)}`,
  `DoctrineFitIn{doctrine, role, ship_type, fit_name="", skillpacks}` (`extra="ignore"`),
  `DoctrinesApiPayload(RootModel[list[...]])`.
- `app/sources/base.py|real.py|demo.py`: `fetch_doctrines()`. Real → `GET doctrine_definitions`;
  demo → `data_demo/doctrine_definitions_api.json`.
- `app/snapshot/models.py`: `DoctrineSkillReq{skill_id, level_yellow, level_green}`,
  `DoctrineFit{doctrine, role, ship_type, fit_name, skills: tuple[DoctrineSkillReq,…]}`;
  add `doctrines: tuple[DoctrineFit, …]` to `Snapshot`.
- `app/queries/doctrine.py` (new, pure): `build_doctrine_fits(payload, catalog)` — flatten,
  dedupe-by-max, **drop skill_ids absent from the SDE catalogue** (log, mirroring trained-skill
  filtering) so expanded queries never fail `validate_refs`; sort by the 4-tuple.
  `find_fit(snapshot, ref)`, `expand_fit(fit, tier) -> GroupNode` (raises if the fit has zero
  skills at the tier), `fit_skill_counts(fit) -> (yellow, green)`, `DoctrineRef`,
  `encode_doctrine_ref`/`decode_doctrine_ref`.
- `app/snapshot/build.py`: `build_snapshot(..., doctrines_payload=[])` builds & stores fits.
- `app/snapshot/store.py`: gather a third fetch, pass to `build_snapshot`.
- `app/api/doctrines.py` (new, role-gated) `GET /api/doctrines` →
  `{fits:[{doctrine, role, ship_type, fit_name, yellow_skill_count, green_skill_count}], snapshot_version, snapshot_fetched_at}`,
  sorted by the 4-tuple. No skill lists shipped (backend expands).
- `app/api/query.py`: `QueryRequest` gains `doctrine: DoctrineRef | None`; `query` becomes
  optional (exactly one required). When `doctrine` is set, expand server-side, run the
  identical `_execute` path, and attach a provenance label. `QueryResponse` gains optional
  `doctrine: DoctrineLabel | None` (set via `model_copy` so the shared cache entry is untouched).
  `GET /api/query/export.csv` accepts `d=<encoded ref>` (alternative to `q=`); CSV gets a
  leading `# Doctrine: …` metadata line when present.

## Sharing / provenance

- Doctrine queries use a compact, stable **`d=`** URL param = base64url of
  `{doctrine, role, ship_type, fit_name, tier}` (not `q=`'s 50-skill blob). Backend & CSV
  decode `d=`, expand, run. Results header / CSV show
  **"BDA / Mainline / Legion / DPS — green (53 skills)"**.

## Frontend

- `api.ts`: `DoctrineFitOut`, `DoctrinesResponse`, `DoctrineRef`, optional `doctrine` on
  `QueryResponse`; `api.doctrines()`, `api.queryDoctrine(ref, groups, inm)`,
  `exportCsvDoctrineUrl(ref, groupsParam, inm)`.
- `query/doctrineRef.ts` (new): encode/decode `DoctrineRef` (mirrors Python) + helpers to
  build cascading option lists and the label string.
- `components/DoctrineSelector.tsx` (new): cascading `doctrine → role → ship_type → fit_name`
  selects (empty `fit_name` rendered as "—"), `( ) Yellow ( ) Green` radio, live skill count,
  Run / Copy link / Export CSV.
- `components/ResultsTable.tsx` (new): extracted from `SkillQuery.tsx` so both modes share it.
- `views/SkillQuery.tsx`: `[ Manual ] [ Doctrine ]` mode toggle; pool filter & include-non-matching
  shared. `d=` param hydrates Doctrine mode + auto-runs (mirrors existing `q=` behavior).

## Demo fixtures & tests

- `scripts/gen_demo_fixtures.py`: also emit `data_demo/doctrine_definitions_api.json` built from
  the demo SDE-fallback catalogue's skill_ids (deterministic; a few fits across 2–3 doctrines/roles,
  ~30–60 skills each, including some `level_yellow=0`).
- Tests (TDD): `build_doctrine_fits` flatten/dedupe/unknown-drop/sort; `expand_fit` tier &
  zero-drop & empty-tier error; `fit_skill_counts`; ref encode/decode round-trip; `/api/doctrines`
  shape & sort; doctrine POST + `d=` CSV integration (incl. provenance label, 404/422 paths);
  snapshot build includes doctrines & drops unknown skill_ids. Frontend: `doctrineRef` codec +
  cascading-option helpers.

## Out of scope

Per-fit readiness breakdown / missing-skill reporting (results stay strict pass/fail, mirroring
the manual builder); editing a doctrine-derived set in the manual tree; combining doctrine + manual
conditions in one query.
