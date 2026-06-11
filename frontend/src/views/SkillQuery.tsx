import { useCallback, useEffect, useMemo, useRef, useState, useReducer } from 'react'
import { api, ApiError, QueryResponse } from '../api'
import { PoolFilter } from '../components/PoolFilter'
import { GroupEditor } from '../components/QueryBuilder/GroupEditor'
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
import { decodeQuery, encodeQuery } from '../query/encode'
import { groupsToParam, parseGroupsParam } from '../query/groups'
import { MAX_DEPTH, MAX_NODES } from '../query/model'
import { builderReducer } from '../query/reducer'

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
  const [root, dispatch] = useReducer(builderReducer, undefined, initialRoot)
  // null until the catalog delivers the vocabulary; then a concrete selection.
  const [selectedGroups, setSelectedGroups] = useState<Set<string> | null>(null)
  const [includeNonMatching, setIncludeNonMatching] = useState(false)
  const [result, setResult] = useState<QueryResponse | null>(null)
  const [queryError, setQueryError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [copied, setCopied] = useState(false)

  const allGroups = useMemo(() => catalog?.character_groups ?? [], [catalog])

  useEffect(() => {
    if (catalog && selectedGroups === null) {
      const g = new URLSearchParams(window.location.search).get('g')
      setSelectedGroups(parseGroupsParam(g, catalog.character_groups))
    }
  }, [catalog, selectedGroups])

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

  const run = useCallback(async () => {
    if (!wire || emptyPool) return
    setRunning(true)
    setQueryError(null)
    try {
      const res = await api.query(wire, groupsList, includeNonMatching)
      setResult(res)
      const params = new URLSearchParams()
      params.set('q', encodeQuery(wire))
      if (groupsParam) params.set('g', groupsParam)
      window.history.replaceState(null, '', `?${params.toString()}`)
    } catch (e) {
      setResult(null)
      setQueryError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }, [wire, emptyPool, groupsList, groupsParam, includeNonMatching])

  // A shared link should show its results without an extra click.
  const autoRan = useRef(false)
  useEffect(() => {
    if (autoRan.current || selectedGroups === null) return
    if (wire && new URLSearchParams(window.location.search).has('q')) {
      autoRan.current = true
      void run()
    }
  }, [wire, run, selectedGroups])

  const copyLink = async () => {
    if (!wire) return
    const params = new URLSearchParams()
    params.set('q', encodeQuery(wire))
    if (groupsParam) params.set('g', groupsParam)
    const url = `${window.location.origin}${window.location.pathname}?${params.toString()}`
    await navigator.clipboard.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

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

      <GroupEditor
        group={root}
        catalog={catalog}
        dispatch={dispatch}
        atNodeCap={nodes >= MAX_NODES}
      />

      {capWarning && <div className="notice">{capWarning}</div>}
      {emptyPool && (
        <div className="notice">Select at least one character group to query.</div>
      )}
      {wire ? (
        <Summary text={describeQuery(wire, skillName)} />
      ) : (
        <div className="query-summary dim">Fill in a condition to run the query.</div>
      )}

      <div className="run-bar">
        <button
          type="button"
          className="btn primary"
          disabled={!wire || running || capWarning !== null || emptyPool}
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
        <button type="button" className="btn" disabled={!wire} onClick={() => void copyLink()}>
          {copied ? 'Copied!' : 'Copy link'}
        </button>
        {wire && !emptyPool && (
          <a
            className="btn"
            href={api.exportCsvUrl(encodeQuery(wire), groupsParam, includeNonMatching)}
            download="skill-query.csv"
          >
            Export CSV
          </a>
        )}
      </div>

      {queryError && <div className="notice error">{queryError}</div>}

      {result && (
        <div className="results">
          <div className="results-meta">
            <span>
              {result.totals.users_with_matches} of {result.totals.total_users} users match ·{' '}
              {result.totals.total_matching_characters} of {result.totals.total_characters}{' '}
              characters in pool
            </span>
            <span>
              snapshot v{result.snapshot_version} ·{' '}
              {new Date(result.snapshot_fetched_at).toLocaleString()}
            </span>
          </div>
          <table>
            <thead>
              <tr>
                <th>User</th>
                <th>Matching characters</th>
                <th className="num">Matches</th>
              </tr>
            </thead>
            <tbody>
              {result.rows.length === 0 && (
                <tr>
                  <td colSpan={3} className="dim">
                    No matches.
                  </td>
                </tr>
              )}
              {result.rows.map((row) => (
                <tr key={row.user_id} className={row.match_count === 0 ? 'zero-match' : ''}>
                  <td>{row.user_name}</td>
                  <td>
                    {row.matching_characters.map((c) => (
                      <span key={c.character_id} className="char-chip">
                        {c.name} <span className="type">{c.group}</span>
                      </span>
                    ))}
                  </td>
                  <td className="num">
                    {row.match_count}/{row.total_characters}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td>{result.totals.users_with_matches} users</td>
                <td />
                <td className="num">{result.totals.total_matching_characters}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  )
}
