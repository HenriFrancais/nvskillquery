// Interactive "characters reachable vs. added skill points" plot. A cumulative
// step line over the per-character SP gaps. The x-axis spans a wide range, so
// the view opens at [0, DEFAULT_X_MAX] and is navigable: drag a region to
// box-zoom (uPlot native), scroll to zoom around the cursor, double-click to
// reset to the default view.

import { useEffect, useRef } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import { DEFAULT_X_MAX, distanceCurve } from './distanceCurve'

const ACCENT = '#4db8ff'
const GRID = 'rgba(138,147,167,0.15)'
const AXIS = '#8893a7'

function fmtSp(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000) return `${Math.round(n / 1_000)}k`
  return `${Math.round(n)}`
}

/**
 * Wheel to zoom the x-axis around the cursor. The listener is torn down in the
 * `destroy` hook so nothing leaks and no stray wheel event reaches a destroyed
 * chart when it is rebuilt or unmounted. (Box-zoom and reset are wired through
 * uPlot's own cursor config, which it cleans up itself.)
 */
function wheelZoomPlugin(): uPlot.Plugin {
  let detach: (() => void) | null = null
  return {
    hooks: {
      ready(u) {
        const over = u.over
        const onWheel = (e: WheelEvent) => {
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
        }
        over.addEventListener('wheel', onWheel, { passive: false })
        detach = () => over.removeEventListener('wheel', onWheel)
      },
      destroy() {
        detach?.()
        detach = null
      },
    },
  }
}

/**
 * Hover readout: a small label that snaps to the nearest step and shows the
 * exact cumulative character count (and the SP value) at the cursor.
 */
function valueTooltipPlugin(): uPlot.Plugin {
  let tip: HTMLDivElement | null = null
  return {
    hooks: {
      ready(u) {
        tip = document.createElement('div')
        tip.className = 'sp-tooltip'
        tip.style.display = 'none'
        u.over.appendChild(tip)
      },
      setCursor(u) {
        if (!tip) return
        const idx = u.cursor.idx
        const x = idx == null ? null : u.data[0][idx]
        const y = idx == null ? null : (u.data[1][idx] as number | null)
        if (idx == null || x == null || y == null) {
          tip.style.display = 'none'
          return
        }
        tip.textContent = `${y} character${y === 1 ? '' : 's'} · ${fmtSp(x)} SP`
        tip.style.display = 'block'
        tip.style.left = `${u.valToPos(x, 'x')}px`
        tip.style.top = `${u.valToPos(y, 'y')}px`
      },
      destroy() {
        tip?.remove()
        tip = null
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

    const opts: uPlot.Options = {
      width: el.clientWidth || 640,
      height: 220,
      cursor: {
        // Native box-zoom: drag a horizontal region to zoom into it. `dist`
        // requires a deliberate drag so a plain click doesn't zoom.
        drag: { x: true, y: false, dist: 5 },
        // Double-click resets to the default view rather than uPlot's auto-fit.
        bind: {
          dblclick: (u) => () => {
            u.setScale('x', { min: 0, max: DEFAULT_X_MAX })
            return null
          },
        },
      },
      legend: { show: false },
      scales: {
        // No range override on x — that would pin the scale and defeat zoom.
        x: { time: false },
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
      plugins: [wheelZoomPlugin(), valueTooltipPlugin()],
    }

    const u = new uPlot(opts, [xs, ys], el)
    plot.current = u
    // Open at the default window; box-zoom / wheel / reset move it from here.
    u.setScale('x', { min: 0, max: DEFAULT_X_MAX })

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
