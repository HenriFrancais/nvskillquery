export function CharTypePicker({
  charTypes,
  value,
  onChange,
}: {
  charTypes: string[]
  value: string | null
  onChange: (charType: string) => void
}) {
  return (
    <select
      aria-label="Character type"
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="" disabled>
        choose type…
      </option>
      {charTypes.map((t) => (
        <option key={t} value={t}>
          {t}
        </option>
      ))}
    </select>
  )
}
