// Typed wrappers for the FastAPI backend.

import type { QueryNode } from './query/model'

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
  char_types: string[]
  snapshot_version: number
  snapshot_fetched_at: string
}

export interface CharacterOut {
  character_id: number
  name: string
  character_type: string
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

export interface QueryResponse {
  rows: UserRow[]
  totals: QueryTotals
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
  query: (query: QueryNode, includeNonMatching: boolean) =>
    jsonFetch<QueryResponse>(`${API}/query`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ query, include_non_matching: includeNonMatching }),
    }),
  exportCsvUrl: (encodedQuery: string, includeNonMatching: boolean) =>
    `${API}/query/export.csv?q=${encodedQuery}&include_non_matching=${includeNonMatching}`,
}
