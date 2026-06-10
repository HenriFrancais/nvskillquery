// Reducer over the builder tree. The root is always a group and is never
// removable; all mutations address nodes by client id.

import {
  BuilderGroup,
  BuilderNode,
  BuilderSkill,
  emptyGroup,
  nextId,
} from './builder'

export type BuilderAction =
  | { type: 'reset'; root: BuilderGroup }
  | { type: 'set_op'; id: string; op: 'and' | 'or' }
  | { type: 'add_condition'; groupId: string }
  | { type: 'add_group'; groupId: string }
  | { type: 'remove'; id: string }
  | {
      type: 'update_condition'
      id: string
      patch: Partial<Pick<BuilderSkill, 'skill_id' | 'min_level'>>
    }

function mapTree(node: BuilderNode, fn: (n: BuilderNode) => BuilderNode): BuilderNode {
  const mapped = fn(node)
  if (mapped.kind !== 'group') return mapped
  return { ...mapped, children: mapped.children.map((c) => mapTree(c, fn)) }
}

function removeFromTree(node: BuilderGroup, id: string): BuilderGroup {
  return {
    ...node,
    children: node.children
      .filter((c) => c.id !== id)
      .map((c) => (c.kind === 'group' ? removeFromTree(c, id) : c)),
  }
}

export function builderReducer(root: BuilderGroup, action: BuilderAction): BuilderGroup {
  switch (action.type) {
    case 'reset':
      return action.root
    case 'set_op':
      return mapTree(root, (n) =>
        n.id === action.id && n.kind === 'group' ? { ...n, op: action.op } : n,
      ) as BuilderGroup
    case 'add_condition': {
      const fresh: BuilderNode = { id: nextId(), kind: 'skill', skill_id: null, min_level: 1 }
      return mapTree(root, (n) =>
        n.id === action.groupId && n.kind === 'group'
          ? { ...n, children: [...n.children, fresh] }
          : n,
      ) as BuilderGroup
    }
    case 'add_group': {
      // New subgroups default to the opposite op of their parent — chaining
      // "(... AND ...) OR (...)" is the common shape.
      return mapTree(root, (n) =>
        n.id === action.groupId && n.kind === 'group'
          ? { ...n, children: [...n.children, emptyGroup(n.op === 'and' ? 'or' : 'and')] }
          : n,
      ) as BuilderGroup
    }
    case 'remove': {
      if (action.id === root.id) return root // root group is never removable
      return removeFromTree(root, action.id)
    }
    case 'update_condition':
      return mapTree(root, (n) => {
        if (n.id !== action.id || n.kind !== 'skill') return n
        return {
          ...n,
          skill_id: action.patch.skill_id !== undefined ? action.patch.skill_id : n.skill_id,
          min_level:
            action.patch.min_level !== undefined ? action.patch.min_level : n.min_level,
        }
      }) as BuilderGroup
  }
}
