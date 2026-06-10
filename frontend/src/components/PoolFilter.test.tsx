import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { PoolFilter } from './PoolFilter'

const GROUPS = ['Home', 'Strat', 'Farm', 'Alpha']

function Harness({ initial }: { initial: string[] }) {
  const [selected, setSelected] = useState(new Set(initial))
  return (
    <PoolFilter
      groups={GROUPS}
      selected={selected}
      onToggle={(name) =>
        setSelected((prev) => {
          const next = new Set(prev)
          if (next.has(name)) next.delete(name)
          else next.add(name)
          return next
        })
      }
    />
  )
}

describe('PoolFilter', () => {
  it('renders one labelled chip per group with selection state', () => {
    render(<Harness initial={['Home', 'Strat']} />)
    for (const g of GROUPS) {
      expect(screen.getByRole('checkbox', { name: g })).toBeInTheDocument()
    }
    expect(screen.getByRole('checkbox', { name: 'Home' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Farm' })).not.toBeChecked()
  })

  it('toggles a group on click', () => {
    render(<Harness initial={['Home']} />)
    fireEvent.click(screen.getByRole('checkbox', { name: 'Strat' }))
    expect(screen.getByRole('checkbox', { name: 'Strat' })).toBeChecked()
    fireEvent.click(screen.getByRole('checkbox', { name: 'Home' }))
    expect(screen.getByRole('checkbox', { name: 'Home' })).not.toBeChecked()
  })
})
