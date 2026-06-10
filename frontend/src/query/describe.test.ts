import { describe, expect, it } from 'vitest'
import { describeQuery } from './describe'
import type { QueryNode } from './model'

const names: Record<number, string> = { 1: 'Capital Hybrid Turret', 2: 'Gunnery Doctrine' }
const skillName = (id: number) => names[id] ?? `#${id}`

describe('describeQuery', () => {
  it('renders leaves', () => {
    expect(
      describeQuery({ kind: 'skill', skill_id: 1, min_level: 4 }, skillName),
    ).toBe('Capital Hybrid Turret ≥ IV')
    expect(describeQuery({ kind: 'char_type', char_type: 'Titan' }, skillName)).toBe(
      'type = Titan',
    )
  })

  it('parenthesises nested groups but not the top level', () => {
    const tree: QueryNode = {
      kind: 'group',
      op: 'or',
      children: [
        {
          kind: 'group',
          op: 'and',
          children: [
            { kind: 'skill', skill_id: 1, min_level: 4 },
            { kind: 'skill', skill_id: 2, min_level: 3 },
          ],
        },
        { kind: 'char_type', char_type: 'Dreadnought' },
      ],
    }
    expect(describeQuery(tree, skillName)).toBe(
      '(Capital Hybrid Turret ≥ IV AND Gunnery Doctrine ≥ III) OR type = Dreadnought',
    )
  })

  it('collapses single-child groups without parens', () => {
    const tree: QueryNode = {
      kind: 'group',
      op: 'and',
      children: [{ kind: 'skill', skill_id: 1, min_level: 1 }],
    }
    expect(describeQuery(tree, skillName)).toBe('Capital Hybrid Turret ≥ I')
  })
})
