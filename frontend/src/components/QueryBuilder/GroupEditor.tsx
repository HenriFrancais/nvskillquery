import { Fragment } from 'react'
import type { Dispatch } from 'react'
import type { CatalogResponse } from '../../api'
import type { BuilderGroup, BuilderNode } from '../../query/builder'
import { MAX_DEPTH } from '../../query/model'
import type { BuilderAction } from '../../query/reducer'
import { LevelSelect } from './LevelSelect'
import { SkillPicker } from './SkillPicker'

const ROMAN = ['', 'I', 'II', 'III', 'IV', 'V']

export function GroupEditor({
  group,
  catalog,
  dispatch,
  depth = 1,
  atNodeCap = false,
}: {
  group: BuilderGroup
  catalog: CatalogResponse
  dispatch: Dispatch<BuilderAction>
  depth?: number
  atNodeCap?: boolean
}) {
  const isRoot = depth === 1
  // A new subgroup needs room for itself plus at least one condition.
  const canNest = depth + 2 <= MAX_DEPTH

  return (
    <div className={`builder-group${group.op === 'or' ? ' op-or' : ''}`}>
      <div className="group-head">
        <div className="op-toggle" role="group" aria-label="Group operator">
          <button
            type="button"
            className={group.op === 'and' ? 'active-and' : ''}
            onClick={() => dispatch({ type: 'set_op', id: group.id, op: 'and' })}
          >
            AND
          </button>
          <button
            type="button"
            className={group.op === 'or' ? 'active-or' : ''}
            onClick={() => dispatch({ type: 'set_op', id: group.id, op: 'or' })}
          >
            OR
          </button>
        </div>
        <div className="group-actions">
          <button
            type="button"
            className="btn subtle"
            disabled={atNodeCap}
            onClick={() => dispatch({ type: 'add_condition', groupId: group.id })}
          >
            + skill
          </button>
          <button
            type="button"
            className="btn subtle"
            disabled={atNodeCap || !canNest}
            onClick={() => dispatch({ type: 'add_group', groupId: group.id })}
          >
            + group
          </button>
        </div>
        {!isRoot && (
          <button
            type="button"
            className="btn remove"
            aria-label="Remove group"
            onClick={() => dispatch({ type: 'remove', id: group.id })}
          >
            ✕
          </button>
        )}
      </div>
      <div className="group-children">
        {group.children.length === 0 && (
          <div className="dim">empty group — add a condition</div>
        )}
        {group.children.map((child, i) => (
          <Fragment key={child.id}>
            {i > 0 && <div className={`joiner ${group.op}`}>{group.op.toUpperCase()}</div>}
            <ChildEditor
              child={child}
              catalog={catalog}
              dispatch={dispatch}
              depth={depth}
              atNodeCap={atNodeCap}
            />
          </Fragment>
        ))}
      </div>
    </div>
  )
}

function ChildEditor({
  child,
  catalog,
  dispatch,
  depth,
  atNodeCap,
}: {
  child: BuilderNode
  catalog: CatalogResponse
  dispatch: Dispatch<BuilderAction>
  depth: number
  atNodeCap: boolean
}) {
  if (child.kind === 'group') {
    return (
      <GroupEditor
        group={child}
        catalog={catalog}
        dispatch={dispatch}
        depth={depth + 1}
        atNodeCap={atNodeCap}
      />
    )
  }

  const skill =
    child.skill_id !== null
      ? catalog.skills.find((s) => s.skill_id === child.skill_id)
      : undefined
  return (
    <div className="condition-row">
      <SkillPicker
        skills={catalog.skills}
        value={child.skill_id}
        onChange={(skillId) =>
          dispatch({ type: 'update_condition', id: child.id, patch: { skill_id: skillId } })
        }
      />
      <LevelSelect
        value={child.min_level}
        onChange={(level) =>
          dispatch({ type: 'update_condition', id: child.id, patch: { min_level: level } })
        }
      />
      <button
        type="button"
        className="btn remove"
        aria-label="Remove condition"
        onClick={() => dispatch({ type: 'remove', id: child.id })}
      >
        ✕
      </button>
      {skill && skill.prerequisites.length > 0 && (
        <span className="prereq-info">
          needs {skill.prerequisites.map((p) => `${p.name} ${ROMAN[p.level]}`).join(', ')}
        </span>
      )}
    </div>
  )
}
