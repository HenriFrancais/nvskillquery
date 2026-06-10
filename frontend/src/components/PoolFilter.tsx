// Character pool filter: which groups of characters the query considers.
// Not part of the query tree — see src/query/groups.ts for the URL form.

export function PoolFilter({
  groups,
  selected,
  onToggle,
}: {
  groups: string[]
  selected: Set<string>
  onToggle: (name: string) => void
}) {
  return (
    <div className="pool-filter">
      <span className="pool-label">Pool</span>
      {groups.map((g) => (
        <label key={g} className={`pool-chip${selected.has(g) ? ' on' : ''}`}>
          <input
            type="checkbox"
            checked={selected.has(g)}
            onChange={() => onToggle(g)}
            aria-label={g}
          />
          {g}
        </label>
      ))}
    </div>
  )
}
