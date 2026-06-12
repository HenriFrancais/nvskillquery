import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { QueryResponse } from '../api'
import { ResultsSummary } from './ResultsSummary'

// uPlot needs a real canvas/layout that jsdom doesn't provide; stub it.
vi.mock('uplot', () => {
  class FakeUplot {
    setScale() {}
    setSize() {}
    destroy() {}
  }
  return {
    default: Object.assign(FakeUplot, {
      paths: { stepped: () => () => undefined },
    }),
  }
})

function makeResult(overrides: Partial<QueryResponse> = {}): QueryResponse {
  return {
    rows: [
      {
        user_id: 1,
        user_name: 'Alice',
        main_character: {
          character_id: 101,
          name: 'Alice',
          group: 'Home',
          matches: true,
        },
        matching_characters: [{ character_id: 101, name: 'Alice', group: 'Home' }],
        match_count: 1,
        total_characters: 2,
      },
    ],
    totals: {
      users_with_matches: 1,
      total_matching_characters: 1,
      total_users: 3,
      total_characters: 5,
    },
    snapshot_version: 7,
    snapshot_fetched_at: '2026-01-01T00:00:00+00:00',
    additional_sp: [8000, 250],
    ...overrides,
  }
}

describe('ResultsSummary', () => {
  beforeEach(() => {
    // jsdom reports zero layout; give the chart container a width.
    Object.defineProperty(HTMLElement.prototype, 'clientWidth', {
      configurable: true,
      get: () => 640,
    })
  })

  it('shows matching Users and Characters counts against pool totals', () => {
    render(<ResultsSummary result={makeResult()} />)
    const users = screen.getByText('Users').closest('.stat-card')!
    const chars = screen.getByText('Characters').closest('.stat-card')!
    expect(users).toHaveTextContent('1 / 3')
    expect(chars).toHaveTextContent('1 / 5')
  })

  it('keeps the match table collapsed until expanded', () => {
    render(<ResultsSummary result={makeResult()} />)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText(/Show all 1 matching users/))
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByText(/Hide all 1 matching users/)).toBeInTheDocument()
  })

  it('replaces the chart with a message when no characters are short of the target', () => {
    render(<ResultsSummary result={makeResult({ additional_sp: [] })} />)
    expect(
      screen.getByText(/Every character in the pool already meets the query/),
    ).toBeInTheDocument()
  })
})
