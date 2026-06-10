// Wire types for the query tree — mirrors app/queries/tree.py. Keep in sync.

export interface SkillCondition {
  kind: 'skill'
  skill_id: number
  min_level: number // 1..5, matches trained level >= min_level
}

export interface CharTypeCondition {
  kind: 'char_type'
  char_type: string
}

export interface GroupNode {
  kind: 'group'
  op: 'and' | 'or'
  children: QueryNode[]
}

export type QueryNode = GroupNode | SkillCondition | CharTypeCondition

export const MAX_DEPTH = 8
export const MAX_NODES = 100
