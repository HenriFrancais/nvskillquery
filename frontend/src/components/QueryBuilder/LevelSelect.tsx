const ROMAN = ['I', 'II', 'III', 'IV', 'V']

export function LevelSelect({
  value,
  onChange,
}: {
  value: number
  onChange: (level: number) => void
}) {
  return (
    <select
      aria-label="Minimum level"
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
    >
      {ROMAN.map((label, i) => (
        <option key={label} value={i + 1}>
          ≥ {label}
        </option>
      ))}
    </select>
  )
}
