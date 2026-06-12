// Results of a run query — shared by the manual and doctrine query modes.

import { QueryResponse } from '../api'
import { doctrineLabel } from '../query/doctrineRef'

export function ResultsTable({ result }: { result: QueryResponse }) {
  return (
    <div className="results">
      <div className="results-meta">
        <span>
          {result.doctrine && (
            <span className="doctrine-label">
              {doctrineLabel(result.doctrine, result.doctrine.skill_count)} ·{' '}
            </span>
          )}
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
  )
}
