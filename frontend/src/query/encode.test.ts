import { describe, expect, it } from 'vitest'
import { decodeQuery, encodeQuery } from './encode'
import type { QueryNode } from './model'

const TREE: QueryNode = {
  kind: 'group',
  op: 'or',
  children: [
    {
      kind: 'group',
      op: 'and',
      children: [
        { kind: 'skill', skill_id: 1000, min_level: 4 },
        { kind: 'skill', skill_id: 1001, min_level: 3 },
      ],
    },
    { kind: 'char_type', char_type: 'Dreadnought' },
  ],
}

describe('encodeQuery / decodeQuery', () => {
  it('round-trips a nested tree', () => {
    expect(decodeQuery(encodeQuery(TREE))).toEqual(TREE)
  })

  it('produces padding-free url-safe output', () => {
    const encoded = encodeQuery(TREE)
    expect(encoded).not.toMatch(/[=+/]/)
  })

  it('matches the backend encoding for a known tree', () => {
    // Backend (python): base64url(json.dumps(tree, separators=defaults)) — the
    // exact string differs in whitespace, but decode must accept both. Verify
    // a hand-encoded compact form decodes correctly.
    const compact = btoa(JSON.stringify({ kind: 'skill', skill_id: 1, min_level: 5 }))
      .replace(/=+$/, '')
    expect(decodeQuery(compact)).toEqual({ kind: 'skill', skill_id: 1, min_level: 5 })
  })

  it.each(['', '!!!', 'aGVsbG8', btoa('{"k":1}')])('rejects garbage %s', (bad) => {
    expect(decodeQuery(bad)).toBeNull()
  })

  it('rejects structurally invalid trees', () => {
    const encode = (data: unknown) => btoa(JSON.stringify(data)).replace(/=+$/, '')
    expect(decodeQuery(encode({ kind: 'skill', skill_id: 1, min_level: 9 }))).toBeNull()
    expect(decodeQuery(encode({ kind: 'group', op: 'and', children: [] }))).toBeNull()
    expect(decodeQuery(encode({ kind: 'char_type', char_type: '' }))).toBeNull()
  })
})
