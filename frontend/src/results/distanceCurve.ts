// Build the cumulative "characters reachable vs. added skill points" curve
// from the per-character SP gaps the backend returns.

export interface CurvePoint {
  x: number // added skill points
  y: number // non-matching characters that would meet the query at this budget
}

// Default upper bound of the x-axis view (added skill points). The chart opens
// at [0, DEFAULT_X_MAX]; users can box-zoom, wheel-zoom, or reset back to it.
export const DEFAULT_X_MAX = 500_000

/**
 * Cumulative step points: at each distinct gap value, y is the number of
 * characters whose gap is at or below that value. Always starts at (0, 0).
 */
export function distanceCurve(gaps: number[]): CurvePoint[] {
  const points: CurvePoint[] = [{ x: 0, y: 0 }]
  const sorted = [...gaps].sort((a, b) => a - b)
  for (let i = 0; i < sorted.length; i++) {
    const x = sorted[i]
    // Collapse runs of equal gaps into one step at the final cumulative count.
    if (i + 1 < sorted.length && sorted[i + 1] === x) continue
    points.push({ x, y: i + 1 })
  }
  return points
}
