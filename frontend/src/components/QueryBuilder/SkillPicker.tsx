import { useMemo, useRef, useState } from 'react'
import type { SkillOut } from '../../api'

export function SkillPicker({
  skills,
  value,
  onChange,
}: {
  skills: SkillOut[]
  value: number | null
  onChange: (skillId: number) => void
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const wrapRef = useRef<HTMLDivElement>(null)

  const selected = value !== null ? skills.find((s) => s.skill_id === value) : undefined

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase()
    const hits = needle
      ? skills.filter(
          (s) =>
            s.name.toLowerCase().includes(needle) ||
            s.group_name.toLowerCase().includes(needle),
        )
      : skills
    const byGroup = new Map<string, SkillOut[]>()
    for (const s of hits) {
      const list = byGroup.get(s.group_name) ?? []
      list.push(s)
      byGroup.set(s.group_name, list)
    }
    return byGroup
  }, [skills, search])

  const pick = (skillId: number) => {
    onChange(skillId)
    setOpen(false)
    setSearch('')
  }

  return (
    <div
      className="skill-picker"
      ref={wrapRef}
      onBlur={(e) => {
        // Close only when focus leaves the picker entirely (not when moving
        // from the input to an option button).
        if (!wrapRef.current?.contains(e.relatedTarget as Node)) setOpen(false)
      }}
    >
      <input
        type="search"
        aria-label="Skill"
        placeholder="search skills…"
        value={open ? search : selected?.name ?? ''}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setSearch(e.target.value)
          setOpen(true)
        }}
      />
      {open && (
        <div className="skill-picker-dropdown">
          {filtered.size === 0 && <div className="skill-picker-group">no matches</div>}
          {[...filtered.entries()].map(([group, groupSkills]) => (
            <div key={group}>
              <div className="skill-picker-group">{group}</div>
              {groupSkills.map((s) => (
                <button
                  key={s.skill_id}
                  type="button"
                  className="skill-picker-option"
                  onClick={() => pick(s.skill_id)}
                >
                  {s.name}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
