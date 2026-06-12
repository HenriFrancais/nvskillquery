import { describe, expect, it } from 'vitest'
import { DEFAULT_X_MAX, distanceCurve } from './distanceCurve'

describe('distanceCurve', () => {
  it('returns a single origin point when there are no gaps', () => {
    expect(distanceCurve([])).toEqual([{ x: 0, y: 0 }])
  })

  it('counts characters reachable at or below each skill-point budget', () => {
    // Two characters need 8000, one needs 250.
    expect(distanceCurve([8000, 8000, 250])).toEqual([
      { x: 0, y: 0 },
      { x: 250, y: 1 },
      { x: 8000, y: 3 },
    ])
  })

  it('collapses duplicate gap values into one cumulative step', () => {
    expect(distanceCurve([5000, 5000, 5000])).toEqual([
      { x: 0, y: 0 },
      { x: 5000, y: 3 },
    ])
  })

  it('is order-independent', () => {
    expect(distanceCurve([300, 100, 200])).toEqual(distanceCurve([100, 200, 300]))
  })
})

describe('DEFAULT_X_MAX', () => {
  it('opens the x-axis at 500k SP', () => {
    expect(DEFAULT_X_MAX).toBe(500_000)
  })
})
