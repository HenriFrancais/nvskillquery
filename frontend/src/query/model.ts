// Wire types for the query tree — mirrors app/queries/tree.py. Keep in sync.
// The tree is skills-only: character groups are a separate pool filter
// (see groups.ts), never a query condition.

export interface SkillCondition {
  kind: 'skill'
  skill_id: number
  min_level: number // 1..5, matches trained level >= min_level
}

export interface GroupNode {
  kind: 'group'
  op: 'and' | 'or'
  children: QueryNode[]
}

export type QueryNode = GroupNode | SkillCondition

export const MAX_DEPTH = 8
export const MAX_NODES = 100
