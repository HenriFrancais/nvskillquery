// Cascading doctrine → role → ship_type → fit_name selector + yellow/green
// tier choice. Auto-fills down to a concrete fit whenever a higher level
// changes, so `value` is always a complete, runnable ref once fits exist.

import { useMemo } from 'react'
import { DoctrineFitOut } from '../api'
import {
  DoctrineRef,
  doctrineOptions,
  fitOptions,
  findFit,
  roleOptions,
  shipOptions,
} from '../query/doctrineRef'

/** Pick the first valid value down each level so the selection is never partial. */
export function resolveDown(
  fits: DoctrineFitOut[],
  tier: 'yellow' | 'green',
  doctrine: string,
  role?: string,
  ship?: string,
  fit?: string,
): DoctrineRef {
  const roles = roleOptions(fits, doctrine)
  const r = role && roles.includes(role) ? role : (roles[0] ?? '')
  const ships = shipOptions(fits, doctrine, r)
  const s = ship && ships.includes(ship) ? ship : (ships[0] ?? '')
  const names = fitOptions(fits, doctrine, r, s)
  const f = fit !== undefined && names.includes(fit) ? fit : (names[0] ?? '')
  return { doctrine, role: r, ship_type: s, fit_name: f, tier }
}

const FIT_PLACEHOLDER = '—'

export function DoctrineSelector({
  fits,
  value,
  onChange,
}: {
  fits: DoctrineFitOut[]
  value: DoctrineRef
  onChange: (next: DoctrineRef) => void
}) {
  const doctrines = useMemo(() => doctrineOptions(fits), [fits])
  const roles = useMemo(() => roleOptions(fits, value.doctrine), [fits, value.doctrine])
  const ships = useMemo(
    () => shipOptions(fits, value.doctrine, value.role),
    [fits, value.doctrine, value.role],
  )
  const names = useMemo(
    () => fitOptions(fits, value.doctrine, value.role, value.ship_type),
    [fits, value.doctrine, value.role, value.ship_type],
  )

  const fit = findFit(fits, value)
  const skillCount = fit
    ? value.tier === 'yellow'
      ? fit.yellow_skill_count
      : fit.green_skill_count
    : 0

  return (
    <div className="doctrine-selector">
      <div className="doctrine-row">
        <label className="doctrine-field">
          <span>Doctrine</span>
          <select
            value={value.doctrine}
            onChange={(e) => onChange(resolveDown(fits, value.tier, e.target.value))}
          >
            {doctrines.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <label className="doctrine-field">
          <span>Role</span>
          <select
            value={value.role}
            onChange={(e) => onChange(resolveDown(fits, value.tier, value.doctrine, e.target.value))}
          >
            {roles.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
        <label className="doctrine-field">
          <span>Ship</span>
          <select
            value={value.ship_type}
            onChange={(e) =>
              onChange(resolveDown(fits, value.tier, value.doctrine, value.role, e.target.value))
            }
          >
            {ships.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label className="doctrine-field">
          <span>Fit</span>
          <select
            value={value.fit_name}
            disabled={names.length <= 1}
            onChange={(e) => onChange({ ...value, fit_name: e.target.value })}
          >
            {names.map((n) => (
              <option key={n} value={n}>
                {n === '' ? FIT_PLACEHOLDER : n}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="doctrine-row">
        <div className="tier-toggle" role="radiogroup" aria-label="Tier">
          <span className="pool-label">Tier</span>
          {(['yellow', 'green'] as const).map((t) => (
            <label key={t} className={`tier-chip tier-${t}${value.tier === t ? ' on' : ''}`}>
              <input
                type="radio"
                name="tier"
                checked={value.tier === t}
                onChange={() => onChange({ ...value, tier: t })}
              />
              {t}
            </label>
          ))}
        </div>
        <span className="dim doctrine-count">
          {fit ? `${skillCount} skills required at ${value.tier}` : 'No doctrine selected'}
        </span>
      </div>
    </div>
  )
}
