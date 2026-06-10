// Shareable-URL encoding: padding-free base64url JSON.
// Mirrors app/queries/encode.py — keep the two in sync.

import type { QueryNode } from './model'

export function encodeQuery(node: QueryNode): string {
  const json = JSON.stringify(node)
  const bytes = new TextEncoder().encode(json)
  let binary = ''
  bytes.forEach((b) => { binary += String.fromCharCode(b) })
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** Returns null for anything that isn't a valid encoded query tree. */
export function decodeQuery(q: string): QueryNode | null {
  let json: string
  try {
    const binary = atob(q.replace(/-/g, '+').replace(/_/g, '/'))
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
  return isQueryNode(data) ? data : null
}

function isQueryNode(data: unknown): data is QueryNode {
  if (typeof data !== 'object' || data === null) return false
  const node = data as Record<string, unknown>
  switch (node.kind) {
    case 'skill':
      return (
        typeof node.skill_id === 'number' &&
        typeof node.min_level === 'number' &&
        node.min_level >= 1 &&
        node.min_level <= 5
      )
    case 'group':
      return (
        (node.op === 'and' || node.op === 'or') &&
        Array.isArray(node.children) &&
        node.children.length > 0 &&
        node.children.every(isQueryNode)
      )
    default:
      return false
  }
}
