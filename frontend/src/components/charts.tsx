import { motion } from 'motion/react'
import { useId, useState } from 'react'
import { useMotionSafe } from '../motion'

/* ---------------------------------------------------------------------------
   Shared chart primitives.

   House rules followed throughout: thin marks, rounded data-ends anchored to
   the baseline, hairline recessive axes, a 2px surface gap between adjacent
   fills, direct labels rather than a number on every point, and text in ink
   tokens rather than the series colour.

   Marks animate from their own baseline via motion, so a bar grows out of the
   axis and a dot arrives at its true position -- never a scale that would
   misrepresent the value mid-flight.
--------------------------------------------------------------------------- */

export type Series = 'vector' | 'keyword' | 'fused'

const SERIES_VAR: Record<Series, string> = {
  vector: 'var(--vector)',
  keyword: 'var(--keyword)',
  fused: 'var(--fused)',
}

export function seriesColor(series: Series) {
  return SERIES_VAR[series]
}

/* -------------------------------------------------------------- ranked bars */

export interface BarDatum {
  key: string | number
  label: string
  value: number
  /** Pre-formatted value shown as the direct label. */
  display: string
  caption?: string
  muted?: boolean
}

export function RankedBars({
  data,
  series,
  max,
  onHover,
}: {
  data: BarDatum[]
  series: Series
  /** Explicit domain max; defaults to the largest value present. */
  max?: number
  onHover?: (key: string | number | null) => void
}) {
  const { markTransition } = useMotionSafe()
  const domain = max ?? Math.max(...data.map((d) => d.value), 0)

  if (data.length === 0) {
    return <p className="empty">No chunk matched any term at this stage.</p>
  }

  return (
    <div className="bars" onMouseLeave={() => onHover?.(null)}>
      {data.map((d, i) => (
        <div
          key={d.key}
          className={`bar-row${d.muted ? ' is-muted' : ''}`}
          onMouseEnter={() => onHover?.(d.key)}
        >
          <span className="bar-rank tnum">{i + 1}</span>
          <span className="bar-label mono">{d.label}</span>
          <div className="bar-track">
            <motion.div
              className="bar-fill"
              style={{ background: SERIES_VAR[series] }}
              initial={{ width: 0 }}
              animate={{
                width: domain > 0 ? `${Math.max((d.value / domain) * 100, 1.5)}%` : '0%',
              }}
              transition={{ ...markTransition, delay: i * 0.05 }}
            />
          </div>
          <span className="bar-value tnum">{d.display}</span>
          {d.caption ? <span className="bar-caption">{d.caption}</span> : null}
        </div>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------- dot plot */

export interface DotDatum {
  key: number
  label: string
  value: number
}

/**
 * Position-encoded ranking for values in a narrow band.
 *
 * L2 distances cluster tightly (e.g. 1.008-1.272), so a zero-anchored bar makes
 * every candidate look identical. A dot plot encodes position rather than
 * length, so it can use a domain that isn't zero-anchored without misleading --
 * provided the axis is drawn, which it is.
 */
export function DotPlot({
  data,
  axisLabel,
  lowerIsBetter = true,
  onHover,
}: {
  data: DotDatum[]
  axisLabel: string
  lowerIsBetter?: boolean
  onHover?: (key: number | null) => void
}) {
  const { markTransition, reduced } = useMotionSafe()

  if (data.length === 0) {
    return <p className="empty">No chunk matched at this stage.</p>
  }

  const values = data.map((d) => d.value)
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const span = hi - lo || 1
  const min = lo - span * 0.18
  const max = hi + span * 0.18
  const pct = (v: number) => ((v - min) / (max - min)) * 100

  const ticks = [min, (min + max) / 2, max]

  return (
    <div className="dotplot" onMouseLeave={() => onHover?.(null)}>
      {data.map((d, i) => (
        <div key={d.key} className="dot-row" onMouseEnter={() => onHover?.(d.key)}>
          <span className="bar-rank tnum">{i + 1}</span>
          <span className="bar-label mono">{d.label}</span>
          <div className="dot-track">
            <span className="dot-rule" />
            <motion.span
              className="dot-mark"
              initial={reduced ? { opacity: 0 } : { left: '0%', opacity: 0 }}
              animate={{ left: `${pct(d.value)}%`, opacity: 1 }}
              transition={{ ...markTransition, delay: i * 0.055 }}
              title={`${d.label}: ${d.value.toFixed(4)}`}
            />
          </div>
          <span className="bar-value tnum">{d.value.toFixed(3)}</span>
        </div>
      ))}
      <div className="dot-axis">
        <span className="dot-rank-spacer" />
        <div className="dot-axis-track">
          {ticks.map((t, i) => (
            <span key={i} className="dot-tick tnum" style={{ left: `${pct(t)}%` }}>
              {t.toFixed(2)}
            </span>
          ))}
        </div>
        <span />
      </div>
      <p className="axis-caption">
        {axisLabel} - {lowerIsBetter ? 'further left is closer' : 'further right is stronger'}
      </p>
    </div>
  )
}

/* ------------------------------------------------------- embedding heatmap */

export function VectorHeatmap({ values }: { values: number[] }) {
  const [hover, setHover] = useState<number | null>(null)
  const { reduced } = useMotionSafe()
  // Symmetric domain so zero sits at the midpoint of the diverging scale.
  const extent = Math.max(...values.map(Math.abs), 1e-6)

  return (
    <div className="heatmap-wrap">
      <div className="heatmap" onMouseLeave={() => setHover(null)}>
        {values.map((v, i) => {
          const t = v / extent
          // Diverging: cool for negative, warm for positive, near-surface at zero.
          const color = t >= 0 ? 'var(--keyword)' : 'var(--vector)'
          const target = 0.15 + Math.abs(t) * 0.85
          return (
            <motion.span
              key={i}
              className={`heat-cell${hover === i ? ' is-on' : ''}`}
              onMouseEnter={() => setHover(i)}
              style={{ background: color }}
              initial={{ opacity: 0 }}
              animate={{ opacity: target }}
              transition={
                reduced ? { duration: 0 } : { duration: 0.4, delay: i * 0.012 }
              }
            />
          )
        })}
      </div>
      <div className="heatmap-foot">
        {hover === null ? (
          <span className="muted">Hover a cell to read its value</span>
        ) : (
          <span className="mono">
            dim[{hover}] = {values[hover].toFixed(4)}
          </span>
        )}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------ PCA scatter */

export function ProjectionPlot({
  question,
  chunks,
  highlight,
  labelFor,
}: {
  question: [number, number]
  chunks: { chunk_id: number; x: number; y: number }[]
  highlight?: number | null
  labelFor: (chunkId: number) => string
}) {
  const clipId = useId().replace(/:/g, '')
  const { reduced, markTransition } = useMotionSafe()
  const size = 320
  const pad = 34
  const inner = size - pad * 2
  const toX = (x: number) => pad + ((x + 1) / 2) * inner
  const toY = (y: number) => pad + (1 - (y + 1) / 2) * inner
  const qx = toX(question[0])
  const qy = toY(question[1])

  return (
    <figure className="figure">
      <svg
        viewBox={`0 0 ${size} ${size}`}
        className="scatter"
        role="img"
        aria-label="Two-dimensional projection of the question and its retrieved chunks"
      >
        <defs>
          <clipPath id={clipId}>
            <rect x={pad - 12} y={pad - 12} width={inner + 24} height={inner + 24} />
          </clipPath>
        </defs>

        {[0.25, 0.5, 0.75].map((f) => (
          <g key={f} stroke="var(--grid)" strokeWidth="1">
            <line x1={pad} x2={size - pad} y1={pad + f * inner} y2={pad + f * inner} />
            <line y1={pad} y2={size - pad} x1={pad + f * inner} x2={pad + f * inner} />
          </g>
        ))}
        <rect
          x={pad}
          y={pad}
          width={inner}
          height={inner}
          fill="none"
          stroke="var(--axis)"
          strokeWidth="1"
        />

        {/* Marks are clipped to the frame; labels deliberately are not, so a
            point near an edge keeps a readable label instead of a fragment. */}
        <g clipPath={`url(#${clipId})`}>
          {chunks.map((c, i) => {
            const on = highlight === c.chunk_id
            return (
              <g key={c.chunk_id}>
                <motion.line
                  x1={qx}
                  y1={qy}
                  x2={toX(c.x)}
                  y2={toY(c.y)}
                  stroke="var(--grid)"
                  strokeWidth="1"
                  initial={reduced ? { opacity: 0 } : { pathLength: 0, opacity: 0 }}
                  animate={{ pathLength: 1, opacity: on ? 0.95 : 0.35 }}
                  transition={{ ...markTransition, delay: 0.15 + i * 0.05 }}
                />
                {/* 2px surface ring keeps overlapping markers separable. */}
                <motion.circle
                  cx={toX(c.x)}
                  cy={toY(c.y)}
                  fill="var(--fused)"
                  stroke="var(--surface)"
                  strokeWidth="2"
                  initial={{ r: 0 }}
                  animate={{ r: on ? 8 : 6 }}
                  transition={{ ...markTransition, delay: 0.25 + i * 0.05 }}
                />
              </g>
            )
          })}
          <motion.circle
            cx={qx}
            cy={qy}
            fill="var(--surface)"
            stroke="var(--ink)"
            strokeWidth="2.5"
            initial={{ r: 0 }}
            animate={{ r: 7 }}
            transition={markTransition}
          />
        </g>

        {chunks.map((c) => {
          const on = highlight === c.chunk_id
          return (
            <text
              key={`l-${c.chunk_id}`}
              x={toX(c.x)}
              y={toY(c.y) - 12}
              className={`scatter-label${on ? ' is-on' : ''}`}
              textAnchor="middle"
            >
              {labelFor(c.chunk_id)}
            </text>
          )
        })}
        {(() => {
          // Keep the label inside the viewBox when the question sits near an edge.
          const anchor = qx < 46 ? 'start' : qx > size - 46 ? 'end' : 'middle'
          const dx = anchor === 'start' ? -10 : anchor === 'end' ? 10 : 0
          return (
            <text
              x={qx + dx}
              y={qy + 22}
              className="scatter-label is-strong"
              textAnchor={anchor}
            >
              question
            </text>
          )
        })()}
      </svg>
      <figcaption>
        The question and its candidate chunks, projected from 1,024 dimensions down
        to two. Positions are meaningful relative to each other within this one
        query only.
      </figcaption>
    </figure>
  )
}

/* ----------------------------------------------------------- rank slopegraph */

export interface SlopeDatum {
  key: number
  label: string
  from: number
  to: number | null
  score: number | null
}

export function RankSlope({
  data,
  fromLabel,
  toLabel,
}: {
  data: SlopeDatum[]
  fromLabel: string
  toLabel: string
}) {
  const { reduced, markTransition } = useMotionSafe()
  const rows = Math.max(...data.map((d) => d.from), 1)
  const h = rows * 44 + 46
  const w = 400
  const leftX = 86
  const rightX = w - 110
  const yFor = (rank: number) => 34 + (rank - 1) * 44

  return (
    <figure className="figure">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="slope"
        role="img"
        aria-label={`Rank change from ${fromLabel} to ${toLabel}`}
      >
        <text x={leftX} y="14" className="slope-head" textAnchor="middle">
          {fromLabel}
        </text>
        <text x={rightX} y="14" className="slope-head" textAnchor="middle">
          {toLabel}
        </text>

        {data.map((d, i) => {
          const kept = d.to !== null
          const y1 = yFor(d.from)
          const y2 = kept ? yFor(d.to as number) : y1
          const mid = (leftX + rightX) / 2
          return (
            <g key={d.key} className={kept ? 'slope-kept' : 'slope-dropped'}>
              {kept ? (
                <motion.path
                  d={`M ${leftX + 24} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${rightX - 24} ${y2}`}
                  fill="none"
                  stroke="var(--fused)"
                  strokeWidth="2"
                  initial={reduced ? { opacity: 0 } : { pathLength: 0 }}
                  animate={{ pathLength: 1, opacity: 1 }}
                  transition={{ ...markTransition, delay: 0.1 + i * 0.09 }}
                />
              ) : (
                <motion.line
                  x1={leftX + 24}
                  y1={y1}
                  x2={leftX + 54}
                  y2={y1}
                  stroke="var(--axis)"
                  strokeWidth="2"
                  strokeLinecap="round"
                  initial={reduced ? { opacity: 0 } : { pathLength: 0 }}
                  animate={{ pathLength: 1, opacity: 1 }}
                  transition={{ ...markTransition, delay: 0.1 + i * 0.09 }}
                />
              )}
              <text x={leftX} y={y1 + 4} className="slope-node mono" textAnchor="middle">
                {d.label}
              </text>
              {kept ? (
                <>
                  <motion.text
                    x={rightX}
                    y={y2 + 4}
                    className="slope-node mono is-kept"
                    textAnchor="middle"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.3, delay: 0.5 + i * 0.09 }}
                  >
                    {d.label}
                  </motion.text>
                  {d.score !== null ? (
                    <motion.text
                      x={rightX + 34}
                      y={y2 + 4}
                      className="slope-score tnum"
                      textAnchor="start"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.3, delay: 0.56 + i * 0.09 }}
                    >
                      {d.score.toFixed(3)}
                    </motion.text>
                  ) : null}
                </>
              ) : (
                <text x={leftX + 64} y={y1 + 4} className="slope-drop-label" textAnchor="start">
                  dropped
                </text>
              )}
            </g>
          )
        })}
      </svg>
      <figcaption>
        Relevance scores come from the reranker, which reads the question and each
        chunk together instead of comparing vectors.
      </figcaption>
    </figure>
  )
}
