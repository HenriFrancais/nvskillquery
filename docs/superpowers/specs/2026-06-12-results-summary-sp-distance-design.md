# Results summary + distance-to-target chart

**Date:** 2026-06-12
**Status:** Approved, in implementation

## Problem

After a query runs we always render a full table of matching users and their
characters. Two changes were requested:

1. **Summary-first results.** Default to a compact summary — a count of matching
   **Users** and matching **Characters** — with the full table available behind
   an expand control.
2. **Distance-to-target chart.** Show how far the *non-matching* characters are
   from meeting the query, so people can spot near-misses that could be trained
   up quickly. An interactive (zoom/pan) line plot: additional skill points on
   the x-axis, count of characters that would then meet the query on the y-axis.

## Design

### Results layout (frontend)

Replace the always-expanded table with a summary-first view (stacked layout):

- Two stat cards — **Users** (`users_with_matches / total_users`) and
  **Characters** (`total_matching_characters / total_characters`), both already
  present in `result.totals`.
- The distance-to-target chart below the cards.
- A collapsible "Show all N matching users" control wrapping the **existing**
  table unchanged, default collapsed.

The results meta line (snapshot version, doctrine label) is retained.
`ResultsTable` is split: a new `ResultsSummary` owns the cards + chart + toggle
and renders the current table as-is when expanded.

### What the chart shows

- **x-axis:** additional skill points trained, applied per character.
- **y-axis:** count of *currently-non-matching* characters that would meet the
  query at that SP budget. Cumulative step line from `(0, 0)`, monotonically
  rising.
- Built from a list of per-character **SP gaps**: for each non-matching pool
  character, the minimal additional SP to satisfy the query. `y(x)` = count of
  gaps `<= x`.
- **Default x-range:** `[0, min(maxGap, 5_000_000)]`. Wheel-zoom + drag-pan,
  free to pan/zoom beyond the default (uPlot).
- Computed over the **whole pool's** non-matching characters, independent of the
  "include users with no matches" checkbox (that flag only affects table rows).
- Empty case: if every pool character already matches, show a message instead of
  an empty chart.

### SP-cost model (backend)

- **Skill rank:** dogma attribute **275** (`skillTimeConstant`), already parsed
  into `attrs` in `scripts/refresh_sde.py`. Emit it as `rank` in the
  `skills.json` artifact. `SkillDef.rank` defaults to `1` when absent, so the
  existing artifact, demo fixtures, and tests keep working; real ranks flow
  through on the `DATA_SOURCE=real` path.
- **SP table** (rank-1 cumulative SP to reach a level), indexed by level 0–5:
  `[0, 250, 1414, 8000, 45255, 256000]`. `sp(rank, level) = rank * table[level]`.
- **Per-character gap** over the query tree (pure function; works for manual and
  doctrine queries since a doctrine expands to a tree):
  - **leaf** `(skill >= L)` → expand the full prerequisite closure into a
    required-level map (recursively, max level per skill).
  - **AND** → union of children's required maps, max level per skill (dedups
    shared skills/prereqs).
  - **OR** → the child branch with the smallest resulting cost *for that
    character*.
  - **gap** = `sum over the required map of max(0, sp(rank, required) - sp(rank, current))`.
    Already-matching characters yield 0 and are excluded from the chart.

### API

Extend the `/query` response with `additional_sp: list[int]` — the gaps for the
non-matching pool characters (length = `total_characters - total_matching_characters`).
One int per character; small. The frontend sorts and builds the cumulative curve
client-side, keeping zoom/pan purely client-side.

*Alternative considered:* backend emits prebuilt curve points. Rejected — raw
gaps are smaller, simpler, and let the chart rescale without round-trips.

### Testing

- Backend SP-cost module: pure, TDD unit tests (SP table, prereq closure, AND/OR
  min/sum, dedup).
- `refresh_sde` rank extraction + catalog parse default.
- Frontend curve-builder: pure helper, unit-tested. Light render test for the
  summary/chart.

## Decisions made without asking (flagged at approval)

- SP gaps cover the whole pool regardless of the include-non-matching checkbox.
- `additional_sp` is added to the existing `/query` response, not a new endpoint.
