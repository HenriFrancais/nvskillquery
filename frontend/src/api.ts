// Typed wrappers for the FastAPI backend.

import type { QueryNode } from './query/model'
import type { DoctrineRef } from './query/doctrineRef'

export interface MeResponse {
  user_name: string
  user_rank: string
  user_teams: string[]
  can_query: boolean
}

export interface PrereqOut {
  skill_id: number
  name: string
  level: number
}

export interface SkillOut {
  skill_id: number
  name: string
  group_id: number
  group_name: string
  prerequisites: PrereqOut[]
}

export interface GroupOut {
  group_id: number
  name: string
}

export interface CatalogResponse {
  skills: SkillOut[]
  groups: GroupOut[]
  character_groups: string[]
  sde_build_number: number
  snapshot_version: number
  snapshot_fetched_at: string
}

export interface CharacterOut {
  character_id: number
  name: string
  group: string
}

export interface MainCharacterOut extends CharacterOut {
  matches: boolean
}

export interface UserRow {
  user_id: number
  user_name: string
  main_character: MainCharacterOut
  matching_characters: CharacterOut[]
  match_count: number
  total_characters: number
}

export interface QueryTotals {
  users_with_matches: number
  total_matching_characters: number
  total_users: number
  total_characters: number
}

export interface DoctrineLabel {
  doctrine: string
  role: string
  ship_type: string
  fit_name: string
  tier: 'yellow' | 'green'
  skill_count: number
}

export interface QueryResponse {
  rows: UserRow[]
  totals: QueryTotals
  snapshot_version: number
  snapshot_fetched_at: string
  // Minimal additional SP for each non-matching pool character to satisfy the
  // query — one entry per non-matching character, unordered. Powers the
  // distance-to-target chart.
  additional_sp: number[]
  // Present only for doctrine-sourced queries; null/absent for manual queries.
  doctrine?: DoctrineLabel | null
}

export interface DoctrineFitOut {
  doctrine: string
  role: string
  ship_type: string
  fit_name: string
  yellow_skill_count: number
  green_skill_count: number
}

export interface DoctrinesResponse {
  fits: DoctrineFitOut[]
  snapshot_version: number
  snapshot_fetched_at: string
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function jsonFetch<T>(input: string, init?: RequestInit): Promise<T> {
  const res = await fetch(input, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

// BASE_URL comes from Vite's `base` config (always ends with "/"). When the app
// is mounted under a path prefix this keeps fetches working under whichever
// path the proxy serves.
const API = `${import.meta.env.BASE_URL}api`

export const api = {
  me: () => jsonFetch<MeResponse>(`${API}/me`),
  catalog: () => jsonFetch<CatalogResponse>(`${API}/catalog`),
  doctrines: () => jsonFetch<DoctrinesResponse>(`${API}/doctrines`),
  query: (query: QueryNode, groups: string[], includeNonMatching: boolean) =>
    jsonFetch<QueryResponse>(`${API}/query`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ query, groups, include_non_matching: includeNonMatching }),
    }),
  queryDoctrine: (doctrine: DoctrineRef, groups: string[], includeNonMatching: boolean) =>
    jsonFetch<QueryResponse>(`${API}/query`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ doctrine, groups, include_non_matching: includeNonMatching }),
    }),
  exportCsvUrl: (encodedQuery: string, groupsParam: string | null, includeNonMatching: boolean) =>
    `${API}/query/export.csv?q=${encodedQuery}` +
    (groupsParam ? `&g=${encodeURIComponent(groupsParam)}` : '') +
    `&include_non_matching=${includeNonMatching}`,
  exportCsvDoctrineUrl: (
    encodedRef: string,
    groupsParam: string | null,
    includeNonMatching: boolean,
  ) =>
    `${API}/query/export.csv?d=${encodedRef}` +
    (groupsParam ? `&g=${encodeURIComponent(groupsParam)}` : '') +
    `&include_non_matching=${includeNonMatching}`,
}
