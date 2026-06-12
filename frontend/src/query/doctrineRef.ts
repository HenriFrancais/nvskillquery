// Doctrine ref: the compact, stable identity (fit + tier) carried in share
// links (&d=) and POST bodies. Mirrors app/queries/doctrine.py — keep in sync.

import type { DoctrineFitOut } from '../api'

export interface DoctrineRef {
  doctrine: string
  role: string
  ship_type: string
  fit_name: string
  tier: 'yellow' | 'green'
}

export function encodeDoctrineRef(ref: DoctrineRef): string {
  const json = JSON.stringify(ref)
  const bytes = new TextEncoder().encode(json)
  let binary = ''
  bytes.forEach((b) => {
    binary += String.fromCharCode(b)
  })
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** Returns null for anything that isn't a valid encoded doctrine ref. */
export function decodeDoctrineRef(d: string): DoctrineRef | null {
  let json: string
  try {
    const binary = atob(d.replace(/-/g, '+').replace(/_/g, '/'))
    const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0))
    json = new TextDecoder().decode(bytes)
  } catch {
    return null
  }
  let data: unknown
  try {
    data = JSON.parse(json)
  } catch {
    return null
  }
  return isDoctrineRef(data) ? data : null
}

function isDoctrineRef(data: unknown): data is DoctrineRef {
  if (typeof data !== 'object' || data === null) return false
  const r = data as Record<string, unknown>
  return (
    typeof r.doctrine === 'string' &&
    typeof r.role === 'string' &&
    typeof r.ship_type === 'string' &&
    typeof r.fit_name === 'string' &&
    (r.tier === 'yellow' || r.tier === 'green')
  )
}

// --- cascading option helpers (doctrine → role → ship_type → fit_name) ---

const sortUnique = (xs: string[]): string[] => Array.from(new Set(xs)).sort()

export function doctrineOptions(fits: DoctrineFitOut[]): string[] {
  return sortUnique(fits.map((f) => f.doctrine))
}

export function roleOptions(fits: DoctrineFitOut[], doctrine: string): string[] {
  return sortUnique(fits.filter((f) => f.doctrine === doctrine).map((f) => f.role))
}

export function shipOptions(fits: DoctrineFitOut[], doctrine: string, role: string): string[] {
  return sortUnique(
    fits.filter((f) => f.doctrine === doctrine && f.role === role).map((f) => f.ship_type),
  )
}

export function fitOptions(
  fits: DoctrineFitOut[],
  doctrine: string,
  role: string,
  ship_type: string,
): string[] {
  return sortUnique(
    fits
      .filter((f) => f.doctrine === doctrine && f.role === role && f.ship_type === ship_type)
      .map((f) => f.fit_name),
  )
}

export function findFit(
  fits: DoctrineFitOut[],
  ref: { doctrine: string; role: string; ship_type: string; fit_name: string },
): DoctrineFitOut | null {
  return (
    fits.find(
      (f) =>
        f.doctrine === ref.doctrine &&
        f.role === ref.role &&
        f.ship_type === ref.ship_type &&
        f.fit_name === ref.fit_name,
    ) ?? null
  )
}

/** "BDA / Mainline / Legion / DPS — green (53 skills)" (empty fit name dropped). */
export function doctrineLabel(ref: DoctrineRef, skillCount: number): string {
  const identity = [ref.doctrine, ref.role, ref.ship_type, ref.fit_name].filter(Boolean).join(' / ')
  return `${identity} — ${ref.tier} (${skillCount} skills)`
}
