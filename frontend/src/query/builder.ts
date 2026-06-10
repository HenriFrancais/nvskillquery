// Builder state: the wire QueryNode tree plus client-only node ids so React
// can address nodes for editing/removal. toWire() strips the ids before the
// tree leaves the browser.

import type { QueryNode } from './model'

export interface BuilderSkill {
  id: string
  kind: 'skill'
  skill_id: number | null // null while the picker is empty
  min_level: number
}

export interface BuilderCharType {
  id: string
  kind: 'char_type'
  char_type: string | null
}

export interface BuilderGroup {
  id: string
  kind: 'group'
  op: 'and' | 'or'
  children: BuilderNode[]
}

export type BuilderNode = BuilderGroup | BuilderSkill | BuilderCharType

let counter = 0
export function nextId(): string {
  // crypto.randomUUID is available in all target browsers; the counter makes
  // ids unique even with a mocked crypto in tests.
  counter += 1
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `node-${counter}`
}

export function emptyGroup(op: 'and' | 'or' = 'and'): BuilderGroup {
  return { id: nextId(), kind: 'group', op, children: [] }
}

/** Wire tree -> builder tree (when restoring from a shared URL). */
export function fromWire(node: QueryNode): BuilderNode {
  switch (node.kind) {
    case 'group':
      return {
        id: nextId(),
        kind: 'group',
        op: node.op,
        children: node.children.map(fromWire),
      }
    case 'skill':
      return { id: nextId(), kind: 'skill', skill_id: node.skill_id, min_level: node.min_level }
    case 'char_type':
      return { id: nextId(), kind: 'char_type', char_type: node.char_type }
  }
}

/**
 * Builder tree -> wire tree. Returns null when the tree is incomplete:
 * unfilled conditions are skipped, and a group with nothing left contributes
 * nothing (the backend requires non-empty groups).
 */
export function toWire(node: BuilderNode): QueryNode | null {
  switch (node.kind) {
    case 'group': {
      const children = node.children
        .map(toWire)
        .filter((c): c is QueryNode => c !== null)
      if (children.length === 0) return null
      return { kind: 'group', op: node.op, children }
    }
    case 'skill':
      if (node.skill_id === null) return null
      return { kind: 'skill', skill_id: node.skill_id, min_level: node.min_level }
    case 'char_type':
      if (node.char_type === null || node.char_type === '') return null
      return { kind: 'char_type', char_type: node.char_type }
  }
}

export function countNodes(node: BuilderNode): number {
  if (node.kind !== 'group') return 1
  return 1 + node.children.reduce((sum, c) => sum + countNodes(c), 0)
}

export function treeDepth(node: BuilderNode): number {
  if (node.kind !== 'group') return 1
  return 1 + Math.max(0, ...node.children.map(treeDepth))
}
