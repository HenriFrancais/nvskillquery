# Skills-only queries, character-group pool filter, SDE catalogue, containerization

Date: 2026-06-10
Status: approved

## Motivation

Three changes to the current (Phase 0–5) implementation:

1. The logical query tree should express **skill requirements only**. Character
   type/group is not a query condition — it scopes which characters are
   considered at all.
2. Character "type" and "group" are the same concept and describe the role of a
   user's character. The starting vocabulary is **Home, Strat, Farm, Alpha**
   (data-driven; new groups appearing upstream must work without code changes).
3. The skill catalogue must come from the **EVE Online SDE**
   (https://developers.eveonline.com/docs/services/static-data/) and skill
   selection must be validated against it. The SDE artifact is refreshed at
   container build time when CCP publishes a new build. The app gets
   containerized following the conventions of the sibling apps (router,
   nvinfo) behind NV Tools.

Breaking changes are acceptable: the upstream API contract is still proposed
(no real implementation exists) and there are no shared query URLs in the wild.

## 1. Query semantics

### Wire model

The query tree is skills-only: `group` nodes (`and`/`or`) whose leaves are all
`skill` conditions (`skill_id`, `min_level` 1–5). The `char_type` condition is
**deleted** from:

- `app/queries/tree.py` (node type, validation, evaluation)
- `app/queries/encode.py` / `frontend/src/query/encode.ts` (decode rejects it)
- `frontend/src/query/model.ts`, `builder.ts`, `reducer.ts`, `describe.ts`
- the `CharTypePicker` component and the builder's `+ type` button

### Pool filter

`POST /api/query` body:

```json
{
  "query": { "kind": "group", "op": "and", "children": [ {"kind": "skill", "skill_id": 3300, "min_level": 4} ] },
  "groups": ["Home", "Strat"],
  "include_non_matching": false
}
```

- `groups`: list of character-group names. Empty or absent = all groups.
  Unknown names are rejected with 422 (the catalog endpoint publishes the
  vocabulary).
- The **pool** is the set of characters whose group is in `groups`. Only pool
  characters are evaluated against the tree, listed as matching chips, or
  counted. `match_count`, `total_characters`, all four totals, and the CSV are
  pool-relative.
- Users with **zero characters in the pool** are dropped from the response.
  `include_non_matching: true` includes them as 0/0 rows (alongside users that
  have pool characters but no matches).
- The **main character** is always shown for identification even when outside
  the pool; its `matches` flag is `false` in that case.

### Share URLs / CSV export

- Frontend URL: `?q=<base64url tree>&g=Home,Strat` (no `g` param = all groups).
- `GET /api/query/export.csv?q=...&g=Home,Strat&include_non_matching=...`.

## 2. Character groups

Rename `character_type` → `group` (and `character_types` → `character_groups`)
across: the upstream users-API contract (`docs/upstream-api.md`), demo
fixtures, snapshot build, API schemas (`CharacterOut.group`,
`CatalogResponse.character_groups`), CSV columns, and UI labels.

- Vocabulary is data-driven: the users API sends `character_groups`; fallback
  is the distinct set seen on characters. Demo fixtures use
  **Home, Strat, Farm, Alpha**.
- UI: a checkbox-chip row above the builder — `Pool: [Home] [Strat] [Farm]
  [Alpha]` — all selected by default. With every chip deselected the Run
  button disables (an empty pool query is meaningless and silently treating
  it as "all" would surprise).

## 3. SDE skill catalogue

### Artifact and cache (nothing committed to git)

`var/sde/` is a gitignored local cache:

```
var/sde/
  manifest.json   # {"buildNumber": <int>}
  skills.json     # processed catalogue, see shape below
```

`skills.json` shape (compact, app-ready):

```json
{
  "sde_build_number": 27123456,
  "skills": [
    { "skill_id": 3300, "name": "Capital Hybrid Turret", "group_id": 255,
      "group_name": "Gunnery",
      "prerequisites": [ {"skill_id": 3301, "level": 5} ] }
  ]
}
```

### Refresh script

`scripts/refresh_sde.py` (stdlib + httpx; modeled on router's
`app/sde/fetch.py`):

1. GET `https://developers.eveonline.com/static-data/tranquility/latest.jsonl`
   → current build number (the `sde` record).
2. If it equals the cached manifest's build number and `skills.json` exists →
   exit 0, no download.
3. Otherwise download
   `https://developers.eveonline.com/static-data/eve-online-static-data-latest-jsonl.zip`
   (~80 MB), extract only `types.jsonl`, `groups.jsonl`, `typeDogma.jsonl`,
   and produce `skills.json`:
   - skill groups = groups with `categoryID == 16`;
   - skills = published types in those groups, English name;
   - prerequisites from `typeDogma` attribute pairs
     (`requiredSkill1/2/3` = attribute ids 182/183/184, levels = 277/278/279);
     prerequisite entries pointing at unpublished/unknown types are dropped.
4. Failure handling: version check fails but cached artifact exists → keep
   cache, warn, exit 0. No cache and download impossible → exit 1 with a clear
   error.

### Catalogue loading and validation

- The backend loads the catalogue from `var/sde/skills.json` at startup
  (`SDE_DIR` setting, default `./var/sde`).
- `DATA_SOURCE=demo`: if no SDE artifact exists, fall back to a small fake
  catalogue committed at `data_demo/sde_skills.json` so demo/dev works
  offline. `DATA_SOURCE=real` with no artifact → fail fast at startup.
- The upstream **skills API contract shrinks to trained levels only**: per
  character `{skill_id, level}`. Its `skills` catalogue array is removed from
  the contract.
- Validation:
  - `/api/query` rejects trees containing skill ids not in the catalogue
    (422 with the offending ids).
  - Snapshot build drops trained skills with ids unknown to the catalogue,
    logging `snapshot.unknown_skill` once per id.
- `/api/catalog` serves the SDE-derived skill list (plus `character_groups`
  from the users API) and gains `sde_build_number`.

## 4. Containerization

Modeled on `~/dev/router/Dockerfile`:

- **Stage 1 (frontend)**: `node:20-alpine`, `npm ci`, `ARG VITE_URL_PREFIX`,
  `npm run build`.
- **Stage 2 (SDE)**: python + httpx; `RUN --mount=type=cache,target=/sde-cache
  python scripts/refresh_sde.py --cache /sde-cache --out /out/sde` — the
  BuildKit cache mount persists the download/processed artifact across builds
  on the same host, so the 80 MB download happens only when CCP ships a new
  build or the cache is cold.
- **Stage 3 (runtime)**: `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`,
  `uv sync --frozen --no-dev` (a `uv.lock` is added to the repo), app code,
  `COPY --from` of the frontend dist and the SDE artifact into
  `/app/var/sde/`, non-root user, `EXPOSE`, uvicorn CMD honoring `$PORT`.
- `docker-compose.yml`: binds `127.0.0.1:8083:8083` (loopback only — Caddy
  on the VM terminates TLS per the NV Tools topology), env passthrough for
  `NV_TOKEN`, `URL_PREFIX`, `DATA_SOURCE`, `SKILLS_API_URL/TOKEN`,
  `USERS_API_URL/TOKEN`.
- `.dockerignore`: `node_modules`, `.venv`, `var/`, `dist`, caches.
- The app already satisfies the NV Tools contract (bearer 401 boundary,
  `X-User-*` identity, CSP `frame-ancestors`, `nv_embed.js` in `index.html`,
  stateless, URL-prefix aware) — no app changes needed for embedding.

## 5. Testing

Backend (pytest):

- Pool filtering: scoped `match_count`/`total_characters`/totals; zero-pool
  users dropped; revived as 0/0 by `include_non_matching`; main outside pool
  shown with `matches=false`; unknown group name → 422; empty `groups` = all.
- Validation: unknown skill id in POST body → 422 listing ids; on the CSV GET,
  a `q` that fails to decode or validate (including legacy `char_type` nodes)
  → 400, matching the existing bad-`q` handling.
- SDE processor: run against small fixture `types/groups/typeDogma` jsonl
  files; assert category-16 filtering, prereq extraction, unpublished
  dropping, manifest short-circuit (no re-download when current).
- Snapshot: unknown trained skill dropped with warning.

Frontend (vitest):

- `encode`/`reducer`/`describe` updated for char_type removal; `g` param
  round-trip in the share URL; GroupEditor without `+ type`; new pool-chip
  component (default all, toggling).

End-to-end: re-run the headless-Chromium drive against demo mode (build a
skills-only query, toggle pool groups, run, share-URL restore), and
`docker compose build && docker compose up` smoke (`/healthz`, 401 boundary,
authed query).

## Out of scope

- Alpha-clone skill ceilings, "active" vs trained levels (unchanged: trained).
- Prerequisite expansion in queries (prereqs remain informational in the
  picker).
- Runtime SDE refresh (build-time only, per decision).
- VM/Caddy provisioning (covered by the deploy skill when we ship).
