import { describe, expect, it } from 'vitest'
import { BuilderGroup, BuilderSkill, emptyGroup, fromWire, toWire } from './builder'
import { builderReducer } from './reducer'

function rootWithSkill(): { root: BuilderGroup; skill: BuilderSkill } {
  let root = emptyGroup('and')
  root = builderReducer(root, { type: 'add_condition', groupId: root.id })
  const skill = root.children[0] as BuilderSkill
  return { root, skill }
}

describe('builderReducer', () => {
  it('adds conditions to the addressed group', () => {
    const { root } = rootWithSkill()
    expect(root.children).toHaveLength(1)
    expect(root.children[0].kind).toBe('skill')
  })

  it('updates a condition by id', () => {
    const { root, skill } = rootWithSkill()
    const next = builderReducer(root, {
      type: 'update_condition',
      id: skill.id,
      patch: { skill_id: 1000, min_level: 4 },
    })
    const updated = next.children[0] as BuilderSkill
    expect(updated.skill_id).toBe(1000)
    expect(updated.min_level).toBe(4)
  })

  it('toggles group op', () => {
    let root = emptyGroup('and')
    root = builderReducer(root, { type: 'set_op', id: root.id, op: 'or' })
    expect(root.op).toBe('or')
  })

  it('adds nested groups with the opposite op', () => {
    let root = emptyGroup('and')
    root = builderReducer(root, { type: 'add_group', groupId: root.id })
    const sub = root.children[0] as BuilderGroup
    expect(sub.kind).toBe('group')
    expect(sub.op).toBe('or')
  })

  it('removes nodes anywhere in the tree but never the root', () => {
    let root = emptyGroup('and')
    root = builderReducer(root, { type: 'add_group', groupId: root.id })
    const sub = root.children[0] as BuilderGroup
    root = builderReducer(root, { type: 'add_condition', groupId: sub.id })
    const leaf = (root.children[0] as BuilderGroup).children[0]

    let next = builderReducer(root, { type: 'remove', id: leaf.id })
    expect((next.children[0] as BuilderGroup).children).toHaveLength(0)

    next = builderReducer(next, { type: 'remove', id: next.id })
    expect(next.kind).toBe('group') // root survived
  })
})

describe('toWire / fromWire', () => {
  it('strips ids and skips unfilled conditions', () => {
    let root = emptyGroup('and')
    root = builderReducer(root, { type: 'add_condition', groupId: root.id })
    root = builderReducer(root, { type: 'add_condition', groupId: root.id })
    const skill = root.children[0] as BuilderSkill
    root = builderReducer(root, {
      type: 'update_condition',
      id: skill.id,
      patch: { skill_id: 7, min_level: 2 },
    })
    // second skill still unfilled -> dropped from the wire tree
    expect(toWire(root)).toEqual({
      kind: 'group',
      op: 'and',
      children: [{ kind: 'skill', skill_id: 7, min_level: 2 }],
    })
  })

  it('returns null when nothing is filled in', () => {
    let root = emptyGroup('and')
    root = builderReducer(root, { type: 'add_group', groupId: root.id })
    expect(toWire(root)).toBeNull()
  })

  it('fromWire(toWire(x)) preserves the wire shape', () => {
    const wire = {
      kind: 'group' as const,
      op: 'or' as const,
      children: [
        { kind: 'skill' as const, skill_id: 1, min_level: 5 },
        {
          kind: 'group' as const,
          op: 'and' as const,
          children: [{ kind: 'skill' as const, skill_id: 2, min_level: 3 }],
        },
      ],
    }
    const rebuilt = fromWire(wire)
    expect(toWire(rebuilt)).toEqual(wire)
  })
})
