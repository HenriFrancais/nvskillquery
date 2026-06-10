// Human-readable rendering of the current query, e.g.
//   (Capital Hybrid Turret >= IV AND Gunnery Doctrine >= III) OR Cynosural Field Theory >= I

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
