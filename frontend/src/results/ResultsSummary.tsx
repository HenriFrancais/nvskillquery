// Summary-first results: matching Users / Characters counts and the
// distance-to-target chart up front, with the full match table behind an
// expandable section.

import { useState } from 'react'
import { QueryResponse } from '../api'
import { ResultsTable } from '../components/ResultsTable'
import { doctrineLabel } from '../query/doctrineRef'
import { SpDistanceChart } from './SpDistanceChart'

function StatCard({ label, value, total }: { label: string; value: number; total: number }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">
        {value}
        <span className="stat-total"> / {total}</span>
      </div>
    </div>
  )
}

export function ResultsSummary({ result }: { result: QueryResponse }) {
  const [expanded, setExpanded] = useState(false)
  const { totals } = result
  const nonMatching = result.additional_sp.length

  return (
    <div className="results">
      <div className="results-meta">
        <span>
          {result.doctrine && (
            <span className="doctrine-label">
              {doctrineLabel(result.doctrine, result.doctrine.skill_count)} ·{' '}
            </span>
          )}
          snapshot v{result.snapshot_version} ·{' '}
          {new Date(result.snapshot_fetched_at).toLocaleString()}
        </span>
      </div>

      <div className="stat-cards">
        <StatCard label="Users" value={totals.users_with_matches} total={totals.total_users} />
        <StatCard
          label="Characters"
          value={totals.total_matching_characters}
          total={totals.total_characters}
        />
      </div>

      <div className="chart-panel">
        <div className="chart-title">Characters reachable vs. added skill points</div>
        {nonMatching === 0 ? (
          <div className="dim chart-empty">
            Every character in the pool already meets the query.
          </div>
        ) : (
          <>
            <SpDistanceChart gaps={result.additional_sp} />
            <div className="chart-hint dim">
              Each step is a non-matching character that would meet the query after training that
              many more skill points. Scroll to zoom, drag to pan.
            </div>
          </>
        )}
      </div>

      <div className="match-details">
        <button
          type="button"
          className="match-toggle"
          aria-expanded={expanded}
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? '▾' : '▸'} {expanded ? 'Hide' : 'Show'} all{' '}
          {totals.users_with_matches} matching users
        </button>
        {expanded && (
          <div className="match-table">
            <ResultsTable result={result} />
          </div>
        )}
      </div>
    </div>
  )
}
