import { fireEvent, render, screen } from '@testing-library/react'
import { useReducer } from 'react'
import { describe, expect, it } from 'vitest'
import type { CatalogResponse } from '../../api'
import type { BuilderGroup } from '../../query/builder'
import { emptyGroup } from '../../query/builder'
import { builderReducer } from '../../query/reducer'
import { GroupEditor } from './GroupEditor'

const catalog: CatalogResponse = {
  skills: [
    {
      skill_id: 11,
      name: 'Gunnery Doctrine',
      group_id: 1,
      group_name: 'Gunnery',
      prerequisites: [],
    },
    {
      skill_id: 12,
      name: 'Capital Hybrid Turret',
      group_id: 1,
      group_name: 'Gunnery',
      prerequisites: [{ skill_id: 11, name: 'Gunnery Doctrine', level: 3 }],
    },
  ],
  groups: [{ group_id: 1, name: 'Gunnery' }],
  char_types: ['Dreadnought', 'Carrier'],
  snapshot_version: 1,
  snapshot_fetched_at: '2026-01-01T00:00:00Z',
}

let lastRoot: BuilderGroup

function Harness({ initial }: { initial: BuilderGroup }) {
  const [root, dispatch] = useReducer(builderReducer, initial)
  lastRoot = root
  return <GroupEditor group={root} catalog={catalog} dispatch={dispatch} />
}

describe('GroupEditor', () => {
  it('adds a skill condition and picks a skill from the dropdown', () => {
    render(<Harness initial={emptyGroup('and')} />)

    fireEvent.click(screen.getByText('+ skill'))
    const input = screen.getByLabelText('Skill')

    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: 'capital' } })
    fireEvent.click(screen.getByText('Capital Hybrid Turret'))

    const child = lastRoot.children[0]
    expect(child).toMatchObject({ kind: 'skill', skill_id: 12, min_level: 1 })
    // Prerequisites of the picked skill are surfaced inline.
    expect(screen.getByText(/needs Gunnery Doctrine III/)).toBeInTheDocument()
  })

  it('toggles the group operator', () => {
    render(<Harness initial={emptyGroup('and')} />)

    fireEvent.click(screen.getByRole('button', { name: 'OR' }))
    expect(lastRoot.op).toBe('or')
  })

  it('adds a char-type condition and selects a type', () => {
    render(<Harness initial={emptyGroup('and')} />)

    fireEvent.click(screen.getByText('+ type'))
    fireEvent.change(screen.getByLabelText('Character type'), {
      target: { value: 'Dreadnought' },
    })

    expect(lastRoot.children[0]).toMatchObject({ kind: 'char_type', char_type: 'Dreadnought' })
  })

  it('removes a condition but never the root group', () => {
    render(<Harness initial={emptyGroup('and')} />)

    expect(screen.queryByLabelText('Remove group')).not.toBeInTheDocument()

    fireEvent.click(screen.getByText('+ skill'))
    fireEvent.click(screen.getByLabelText('Remove condition'))

    expect(lastRoot.children).toHaveLength(0)
    expect(screen.getByText(/empty group/)).toBeInTheDocument()
  })

  it('adds a nested subgroup with the opposite operator', () => {
    render(<Harness initial={emptyGroup('and')} />)

    fireEvent.click(screen.getByText('+ group'))

    const child = lastRoot.children[0]
    expect(child).toMatchObject({ kind: 'group', op: 'or' })
    // The nested group gets its own remove button.
    expect(screen.getByLabelText('Remove group')).toBeInTheDocument()
  })
})
