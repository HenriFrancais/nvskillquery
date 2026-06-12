import { useCallback, useEffect, useMemo, useRef, useState, useReducer } from 'react'
import { api, ApiError, DoctrineFitOut, QueryResponse } from '../api'
import { DoctrineSelector, resolveDown } from '../components/DoctrineSelector'
import { PoolFilter } from '../components/PoolFilter'
import { GroupEditor } from '../components/QueryBuilder/GroupEditor'
import { ResultsSummary } from '../results/ResultsSummary'
import { useCatalog } from '../hooks/useCatalog'
import {
  BuilderGroup,
  countNodes,
  fromWire,
  nextId,
  toWire,
  treeDepth,
} from '../query/builder'
import { describeQuery } from '../query/describe'
import {
  DoctrineRef,
  decodeDoctrineRef,
  doctrineLabel,
  doctrineOptions,
  encodeDoctrineRef,
  findFit,
} from '../query/doctrineRef'
import { decodeQuery, encodeQuery } from '../query/encode'
import { groupsToParam, parseGroupsParam } from '../query/groups'
import { MAX_DEPTH, MAX_NODES } from '../query/model'
import { builderReducer } from '../query/reducer'

type Mode = 'manual' | 'doctrine'

function initialMode(): Mode {
  return new URLSearchParams(window.location.search).has('d') ? 'doctrine' : 'manual'
}

function initialRoot(): BuilderGroup {
  const q = new URLSearchParams(window.location.search).get('q')
  if (q) {
    const wire = decodeQuery(q)
    if (wire) {
      const restored = fromWire(wire)
      if (restored.kind === 'group') return restored
      return { id: nextId(), kind: 'group', op: 'and', children: [restored] }
    }
  }
  return {
    id: nextId(),
    kind: 'group',
    op: 'and',
    children: [{ id: nextId(), kind: 'skill', skill_id: null, min_level: 1 }],
  }
}

/** Colorize AND/OR keywords in the describeQuery() output. */
function Summary({ text }: { text: string }) {
  const parts = text.split(/( AND | OR )/)
  return (
    <div className="query-summary">
      {parts.map((p, i) =>
        p === ' AND ' ? (
          <span key={i} className="kw-and">
            {' AND '}
          </span>
        ) : p === ' OR ' ? (
          <span key={i} className="kw-or">
            {' OR '}
          </span>
        ) : (
          p
        ),
      )}
    </div>
  )
}

export function SkillQuery() {
  const { catalog, error: catalogError } = useCatalog(true)
  const [mode, setMode] = useState<Mode>(initialMode)
  const [root, dispatch] = useReducer(builderReducer, undefined, initialRoot)
  const [doctrineFits, setDoctrineFits] = useState<DoctrineFitOut[] | null>(null)
  const [docSel, setDocSel] = useState<DoctrineRef | null>(null)
  // null until the catalog delivers the vocabulary; then a concrete selection.
  const [selectedGroups, setSelectedGroups] = useState<Set<string> | null>(null)
  const [includeNonMatching, setIncludeNonMatching] = useState(false)
  const [result, setResult] = useState<QueryResponse | null>(null)
  const [queryError, setQueryError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [copied, setCopied] = useState(false)

  const allGroups = useMemo(() => catalog?.character_groups ?? [], [catalog])

  useEffect(() => {
    api.doctrines().then(
      (r) => setDoctrineFits(r.fits),
      () => setDoctrineFits([]),
    )
  }, [])

  useEffect(() => {
    if (catalog && selectedGroups === null) {
      const g = new URLSearchParams(window.location.search).get('g')
      setSelectedGroups(parseGroupsParam(g, catalog.character_groups))
    }
  }, [catalog, selectedGroups])

  // Seed the doctrine selection from the URL (&d=) or default to the first fit.
  useEffect(() => {
    if (!doctrineFits || doctrineFits.length === 0 || docSel !== null) return
    const d = new URLSearchParams(window.location.search).get('d')
    const decoded = d ? decodeDoctrineRef(d) : null
    if (decoded) {
      setDocSel(
        resolveDown(
          doctrineFits,
          decoded.tier,
          decoded.doctrine,
          decoded.role,
          decoded.ship_type,
          decoded.fit_name,
        ),
      )
    } else {
      setDocSel(resolveDown(doctrineFits, 'green', doctrineOptions(doctrineFits)[0]))
    }
  }, [doctrineFits, docSel])

  const wire = useMemo(() => toWire(root), [root])
  const nodes = countNodes(root)
  const depth = treeDepth(root)
  const capWarning =
    nodes > MAX_NODES
      ? `Query has ${nodes} conditions; the limit is ${MAX_NODES}.`
      : depth > MAX_DEPTH
        ? `Query is nested ${depth} levels deep; the limit is ${MAX_DEPTH}.`
        : null
  const emptyPool = selectedGroups !== null && selectedGroups.size === 0

  const skillName = useMemo(() => {
    const byId = new Map((catalog?.skills ?? []).map((s) => [s.skill_id, s.name]))
    return (id: number) => byId.get(id) ?? `skill #${id}`
  }, [catalog])

  // Pool selection as the API list ([] = all) and as the URL param (null = all).
  const groupsList = useMemo(() => {
    if (!selectedGroups || selectedGroups.size >= allGroups.length) return []
    return allGroups.filter((g) => selectedGroups.has(g))
  }, [selectedGroups, allGroups])
  const groupsParam = selectedGroups ? groupsToParam(selectedGroups, allGroups) : null

  // The doctrine fit currently selected and its skill count at the chosen tier.
  const docFit = docSel && doctrineFits ? findFit(doctrineFits, docSel) : null
  const docSkillCount = docFit
    ? docSel!.tier === 'yellow'
      ? docFit.yellow_skill_count
      : docFit.green_skill_count
    : 0
  const docRunnable = mode === 'doctrine' && !!docSel && !!docFit && docSkillCount > 0

  const writeUrl = useCallback(() => {
    const params = new URLSearchParams()
    if (mode === 'manual' && wire) params.set('q', encodeQuery(wire))
    if (mode === 'doctrine' && docSel) params.set('d', encodeDoctrineRef(docSel))
    if (groupsParam) params.set('g', groupsParam)
    return params
  }, [mode, wire, docSel, groupsParam])

  const run = useCallback(async () => {
    if (emptyPool) return
    if (mode === 'manual' && !wire) return
    if (mode === 'doctrine' && !docRunnable) return
    setRunning(true)
    setQueryError(null)
    try {
      const res =
        mode === 'doctrine'
          ? await api.queryDoctrine(docSel!, groupsList, includeNonMatching)
          : await api.query(wire!, groupsList, includeNonMatching)
      setResult(res)
      window.history.replaceState(null, '', `?${writeUrl().toString()}`)
    } catch (e) {
      setResult(null)
      setQueryError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }, [mode, wire, docSel, docRunnable, emptyPool, groupsList, includeNonMatching, writeUrl])

  // A shared link should show its results without an extra click.
  const autoRan = useRef(false)
  useEffect(() => {
    if (autoRan.current || selectedGroups === null) return
    const params = new URLSearchParams(window.location.search)
    if (mode === 'manual' && wire && params.has('q')) {
      autoRan.current = true
      void run()
    } else if (mode === 'doctrine' && docRunnable && params.has('d')) {
      autoRan.current = true
      void run()
    }
  }, [mode, wire, docRunnable, run, selectedGroups])

  const switchMode = (next: Mode) => {
    if (next === mode) return
    setMode(next)
    setResult(null)
    setQueryError(null)
  }

  const copyLink = async () => {
    const url = `${window.location.origin}${window.location.pathname}?${writeUrl().toString()}`
    await navigator.clipboard.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const csvHref =
    mode === 'doctrine'
      ? docSel && docRunnable
        ? api.exportCsvDoctrineUrl(encodeDoctrineRef(docSel), groupsParam, includeNonMatching)
        : null
      : wire
        ? api.exportCsvUrl(encodeQuery(wire), groupsParam, includeNonMatching)
        : null

  const runDisabled =
    running ||
    emptyPool ||
    (mode === 'manual' ? !wire || capWarning !== null : !docRunnable)

  if (catalogError) {
    return <div className="centered dim">Failed to load catalog: {catalogError}</div>
  }
  if (!catalog || selectedGroups === null) {
    return <div className="centered dim">Loading catalog…</div>
  }

  return (
    <div className="skill-query">
      <div className="page-header">
        <h1>NV Skill Query</h1>
        <span className="dim">
          SDE build {catalog.sde_build_number} · snapshot v{catalog.snapshot_version} ·{' '}
          {new Date(catalog.snapshot_fetched_at).toLocaleString()}
        </span>
      </div>

      <div className="mode-tabs" role="tablist" aria-label="Query source">
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'manual'}
          className={`mode-tab${mode === 'manual' ? ' on' : ''}`}
          onClick={() => switchMode('manual')}
        >
          Manual
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'doctrine'}
          className={`mode-tab${mode === 'doctrine' ? ' on' : ''}`}
          onClick={() => switchMode('doctrine')}
        >
          Doctrine
        </button>
      </div>

      <PoolFilter
        groups={allGroups}
        selected={selectedGroups}
        onToggle={(name) =>
          setSelectedGroups((prev) => {
            const next = new Set(prev)
            if (next.has(name)) next.delete(name)
            else next.add(name)
            return next
          })
        }
      />

      {mode === 'manual' ? (
        <>
          <GroupEditor
            group={root}
            catalog={catalog}
            dispatch={dispatch}
            atNodeCap={nodes >= MAX_NODES}
          />
          {capWarning && <div className="notice">{capWarning}</div>}
          {wire ? (
            <Summary text={describeQuery(wire, skillName)} />
          ) : (
            <div className="query-summary dim">Fill in a condition to run the query.</div>
          )}
        </>
      ) : (
        <>
          {doctrineFits === null ? (
            <div className="query-summary dim">Loading doctrines…</div>
          ) : doctrineFits.length === 0 ? (
            <div className="query-summary dim">No doctrine definitions available.</div>
          ) : docSel ? (
            <>
              <DoctrineSelector fits={doctrineFits} value={docSel} onChange={setDocSel} />
              <Summary text={docSel ? doctrineLabel(docSel, docSkillCount) : ''} />
            </>
          ) : null}
        </>
      )}

      {emptyPool && (
        <div className="notice">Select at least one character group to query.</div>
      )}

      <div className="run-bar">
        <button
          type="button"
          className="btn primary"
          disabled={runDisabled}
          onClick={() => void run()}
        >
          {running ? 'Running…' : 'Run query'}
        </button>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={includeNonMatching}
            onChange={(e) => setIncludeNonMatching(e.target.checked)}
          />
          include users with no matches
        </label>
        <button
          type="button"
          className="btn"
          disabled={mode === 'manual' ? !wire : !docRunnable}
          onClick={() => void copyLink()}
        >
          {copied ? 'Copied!' : 'Copy link'}
        </button>
        {csvHref && !emptyPool && (
          <a className="btn" href={csvHref} download="skill-query.csv">
            Export CSV
          </a>
        )}
      </div>

      {queryError && <div className="notice error">{queryError}</div>}

      {result && <ResultsSummary result={result} />}
    </div>
  )
}
