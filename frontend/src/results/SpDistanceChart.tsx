// Interactive "characters reachable vs. added skill points" plot. A cumulative
// step line over the per-character SP gaps, with wheel-zoom and drag-pan on the
// x-axis (which spans a wide range). The default view caps at 5M SP; the user
// can freely zoom or pan beyond it.

import { useEffect, useRef } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import { defaultXMax, distanceCurve } from './distanceCurve'

const ACCENT = '#4db8ff'
const GRID = 'rgba(138,147,167,0.15)'
const AXIS = '#8893a7'

function fmtSp(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000) return `${Math.round(n / 1_000)}k`
  return `${Math.round(n)}`
}

/** Wheel to zoom the x-axis around the cursor; drag to pan it. */
function interactionPlugin(): uPlot.Plugin {
  return {
    hooks: {
      ready(u) {
        const over = u.over
        over.addEventListener(
          'wheel',
          (e: WheelEvent) => {
            e.preventDefault()
            const { left, width } = over.getBoundingClientRect()
            const cursorX = e.clientX - left
            const xVal = u.posToVal(cursorX, 'x')
            const min = u.scales.x.min ?? 0
            const max = u.scales.x.max ?? 1
            const factor = e.deltaY < 0 ? 0.8 : 1.25
            const leftFrac = cursorX / width
            const nextSpan = (max - min) * factor
            let nextMin = xVal - leftFrac * nextSpan
            let nextMax = xVal + (1 - leftFrac) * nextSpan
            if (nextMin < 0) {
              nextMax -= nextMin
              nextMin = 0
            }
            u.setScale('x', { min: nextMin, max: nextMax })
          },
          { passive: false },
        )

        over.addEventListener('mousedown', (e: MouseEvent) => {
          if (e.button !== 0) return
          e.preventDefault()
          const { width } = over.getBoundingClientRect()
          const startX = e.clientX
          const min0 = u.scales.x.min ?? 0
          const max0 = u.scales.x.max ?? 1
          const perPx = (max0 - min0) / width
          const onMove = (me: MouseEvent) => {
            const dx = (me.clientX - startX) * perPx
            let nextMin = min0 - dx
            let nextMax = max0 - dx
            if (nextMin < 0) {
              nextMax -= nextMin
              nextMin = 0
            }
            u.setScale('x', { min: nextMin, max: nextMax })
          }
          const onUp = () => {
            document.removeEventListener('mousemove', onMove)
            document.removeEventListener('mouseup', onUp)
          }
          document.removeEventListener('mousemove', onMove)
          document.addEventListener('mousemove', onMove)
          document.addEventListener('mouseup', onUp)
        })
      },
    },
  }
}

export function SpDistanceChart({ gaps }: { gaps: number[] }) {
  const ref = useRef<HTMLDivElement>(null)
  const plot = useRef<uPlot | null>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const points = distanceCurve(gaps)
    const xs = points.map((p) => p.x)
    const ys = points.map((p) => p.y)
    const xMax = defaultXMax(gaps)

    const opts: uPlot.Options = {
      width: el.clientWidth || 640,
      height: 220,
      cursor: { drag: { x: false, y: false } },
      legend: { show: false },
      scales: {
        x: { time: false, range: () => [0, xMax] },
        y: { range: (_u, _min, max) => [0, Math.max(1, max)] },
      },
      axes: [
        {
          stroke: AXIS,
          grid: { stroke: GRID },
          ticks: { stroke: GRID },
          values: (_u, splits) => splits.map(fmtSp),
        },
        {
          stroke: AXIS,
          grid: { stroke: GRID },
          ticks: { stroke: GRID },
          size: 50,
        },
      ],
      series: [
        { label: 'Added SP', value: (_u, v) => (v == null ? '' : fmtSp(v)) },
        {
          label: 'Characters',
          stroke: ACCENT,
          width: 2,
          fill: 'rgba(77,184,255,0.12)',
          points: { show: false },
          paths: uPlot.paths.stepped!({ align: 1 }),
        },
      ],
      plugins: [interactionPlugin()],
    }

    const u = new uPlot(opts, [xs, ys], el)
    plot.current = u
    // The default range() fires on init; setScale makes the cap the live view.
    u.setScale('x', { min: 0, max: xMax })

    const onResize = () => u.setSize({ width: el.clientWidth || 640, height: 220 })
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      u.destroy()
      plot.current = null
    }
  }, [gaps])

  return <div className="sp-chart" ref={ref} />
}
