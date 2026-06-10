// Human-readable rendering of the current query, e.g.
//   (Capital Hybrid Turret >= 4 AND Gunnery Doctrine >= 3) OR type = Dreadnought

import type { QueryNode } from './model'

const ROMAN = ['', 'I', 'II', 'III', 'IV', 'V']

export function describeQuery(
  node: QueryNode,
  skillName: (id: number) => string,
  topLevel = true,
): string {
  switch (node.kind) {
    case 'skill':
      return `${skillName(node.skill_id)} ≥ ${ROMAN[node.min_level]}`
    case 'char_type':
      return `type = ${node.char_type}`
    case 'group': {
      const joiner = node.op === 'and' ? ' AND ' : ' OR '
      const inner = node.children
        .map((c) => describeQuery(c, skillName, false))
        .join(joiner)
      if (node.children.length === 1) return inner
      return topLevel ? inner : `(${inner})`
    }
  }
}
