// The full per-user match table. Rendered inside ResultsSummary's expandable
// section — the meta line and totals live on the summary, not here.

import { QueryResponse } from '../api'

export function ResultsTable({ result }: { result: QueryResponse }) {
  return (
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
  )
}
