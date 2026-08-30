import { motion } from 'motion/react'
import { useState, type ReactNode } from 'react'
import { STAGE_LABELS, STAGE_ORDER, type AskResponse } from '../api'
import { springSoft, useMotionSafe } from '../motion'
import {
  DotPlot,
  ProjectionPlot,
  RankSlope,
  RankedBars,
  VectorHeatmap,
  type BarDatum,
  type DotDatum,
  type SlopeDatum,
} from './charts'

function Scene({
  index,
  title,
  lede,
  aside,
  children,
}: {
  index: number
  title: string
  lede: ReactNode
  aside?: ReactNode
  children: ReactNode
}) {
  const { reduced } = useMotionSafe()
  // The copy and the visual arrive a beat apart, so the eye lands on the
  // explanation first and the chart resolves into it.
  const enter = (delay: number) => ({
    initial: reduced ? { opacity: 0 } : { opacity: 0, y: 26 },
    whileInView: { opacity: 1, y: 0 },
    viewport: { once: true, amount: 0.2, margin: '0px 0px -10% 0px' },
    transition: { ...springSoft, delay: reduced ? 0 : delay },
  })

  return (
    <section className="scene">
      <motion.div className="scene-copy" {...enter(0)}>
        <span className="scene-index tnum">{String(index).padStart(2, '0')}</span>
        <h2>{title}</h2>
        <div className="scene-lede">{lede}</div>
        {aside ? <div className="scene-aside">{aside}</div> : null}
      </motion.div>
      <motion.div className="scene-viz" {...enter(0.1)}>
        {children}
      </motion.div>
    </section>
  )
}

const label = (chunkIndex: number) => `#${chunkIndex}`

export function Walkthrough({ result }: { result: AskResponse }) {
  const s = result.stages
  const [hover, setHover] = useState<string | number | null>(null)

  const byId = new Map<number, number>()
  for (const c of s.fusion.candidates) byId.set(c.chunk_id, c.chunk_index)

  // Distances sit in a narrow band, so these are positions on an axis rather
  // than zero-anchored lengths -- see DotPlot.
  const vectorDots: DotDatum[] = s.vector_search.candidates.map((c) => ({
    key: c.chunk_id,
    label: label(c.chunk_index),
    value: c.distance,
  }))

  const keywordBars: BarDatum[] = s.keyword_search.candidates.map((c) => ({
    key: c.chunk_id,
    label: label(c.chunk_index),
    value: c.score,
    display: c.score.toFixed(4),
  }))

  const slope: SlopeDatum[] = [
    ...s.rerank.kept.map((c) => ({
      key: c.chunk_id,
      label: label(c.chunk_index),
      from: c.previous_rank ?? 1,
      to: c.rank ?? null,
      score: c.relevance_score,
    })),
    ...s.rerank.dropped.map((c) => ({
      key: c.chunk_id,
      label: label(c.chunk_index),
      from: c.previous_rank ?? 1,
      to: null,
      score: null,
    })),
  ].sort((a, b) => a.from - b.from)

  const RETRIEVAL_STAGES = ['embed', 'vector_search', 'keyword_search', 'fusion', 'rerank']
  const retrievalMs = RETRIEVAL_STAGES.reduce((sum, k) => sum + (result.timings[k] ?? 0), 0)
  const modelMs = (result.timings.generate ?? 0) + (result.timings.verify ?? 0)
  const retrievalShare = Math.round((retrievalMs / (result.timings.total || 1)) * 100)
  const maxTiming = Math.max(...STAGE_ORDER.map((k) => result.timings[k] ?? 0), 1)

  const bothCount = s.fusion.candidates.filter((c) => c.found_by_both).length
  const keywordEmpty = s.keyword_search.candidates.length === 0

  return (
    <div id="walkthrough" className="walkthrough">
      <motion.div
        className="walkthrough-head"
        initial={{ opacity: 0, y: 18 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.4 }}
        transition={springSoft}
      >
        <h2>How that answer was produced</h2>
        <p>
          Every number below is from the query you just ran - scroll through the
          seven stages the question passed through, and what each one cost.
        </p>
      </motion.div>

      {/* ------------------------------------------------------------ 1 */}
      <Scene
        index={1}
        title="Your question becomes a vector"
        lede={
          <>
            <p>
              Text can&rsquo;t be compared mathematically, so the question is passed
              through an embedding model that returns{' '}
              <strong>{s.embed.dimensions.toLocaleString()} numbers</strong>. Together
              they place the question at a single point in meaning-space, where
              &ldquo;nearby&rdquo; means &ldquo;about a similar thing.&rdquo;
            </p>
            <p>
              Two sentences sharing no words at all can land close together. That is
              the whole reason this stage exists.
            </p>
          </>
        }
        aside={
          <dl className="facts">
            <div><dt>Model</dt><dd className="mono">{s.embed.model}</dd></div>
            <div><dt>Dimensions</dt><dd className="tnum">{s.embed.dimensions.toLocaleString()}</dd></div>
            <div><dt>Took</dt><dd className="tnum">{Math.round(result.timings.embed)}ms</dd></div>
          </dl>
        }
      >
        <VectorHeatmap values={s.embed.preview} />
        <p className="viz-note">
          The first {s.embed.preview.length} of {s.embed.dimensions.toLocaleString()}{' '}
          dimensions. Warm cells are positive, cool cells negative, intensity is
          magnitude.
        </p>
      </Scene>

      {/* ------------------------------------------------------------ 2 */}
      <Scene
        index={2}
        title="Search one: find the nearest vectors"
        lede={
          <>
            <p>
              Every chunk of the document was embedded the same way when it was
              ingested. Postgres measures the distance from the question&rsquo;s vector
              to all of them and returns the closest{' '}
              <strong>{s.vector_search.top_k}</strong>.
            </p>
            <p>
              This finds meaning rather than wording, which is its strength and
              also its weakness. It has no special respect for exact terms, names, or
              acronyms.
            </p>
          </>
        }
        aside={
          <p className="muted">
            Distances land in a narrow band, so these are plotted as positions on a
            shared axis rather than bars - the differences are what matter.
          </p>
        }
      >
        <DotPlot
          data={vectorDots}
          axisLabel="L2 distance in embedding space"
          onHover={setHover}
        />
        <ProjectionPlot
          question={s.embed.projection.question}
          chunks={s.embed.projection.chunks}
          highlight={typeof hover === 'number' ? hover : null}
          labelFor={(id) => label(byId.get(id) ?? 0)}
        />
      </Scene>

      {/* ------------------------------------------------------------ 3 */}
      <Scene
        index={3}
        title="Search two: find the matching words"
        lede={
          <>
            <p>
              At the same time, a full-text search scores the same chunks on literal
              term overlap, after stemming and stopword removal. No embeddings are
              involved.
            </p>
            <p>
              {keywordEmpty ? (
                <>This question produced no keyword matches at all, so fusion
                below has only one list to work with.</>
              ) : (
                <>
                  Compare the ordering to the previous stage. The two searches{' '}
                  <strong>disagree</strong>, and that disagreement is precisely why
                  running both beats running either.
                </>
              )}
            </p>
          </>
        }
        aside={<p className="muted">Higher <code>ts_rank</code> means more, and denser, term matches.</p>}
      >
        <RankedBars data={keywordBars} series="keyword" onHover={setHover} />
      </Scene>

      {/* ------------------------------------------------------------ 4 */}
      <Scene
        index={4}
        title="Reconciling two disagreeing lists"
        lede={
          <>
            <p>
              The two searches produce scores that mean completely different things
              - a distance and a term-frequency rank can&rsquo;t be added together.
              Reciprocal Rank Fusion sidesteps this by throwing the scores away and
              keeping only the <strong>positions</strong>.
            </p>
            <p>
              Each list contributes <code>1 / (k + rank)</code>, with{' '}
              <code>k = {s.fusion.k}</code>. A chunk found by both searches collects
              from both, so it rises above one that only appeared in a single list.
            </p>
          </>
        }
        aside={
          <p className="muted">
            {bothCount} of {s.fusion.candidates.length} candidates were found by both
            searches.
          </p>
        }
      >
        <div className="fusion-table" role="table" aria-label="Reciprocal rank fusion working">
          <div className="fusion-head" role="row">
            <span role="columnheader">Chunk</span>
            <span role="columnheader">Vector</span>
            <span role="columnheader">Keyword</span>
            <span role="columnheader">Contributions</span>
            <span role="columnheader">Score</span>
          </div>
          {s.fusion.candidates.map((c, i) => {
            const total = s.fusion.candidates[0]?.score || 1
            return (
              <div
                key={c.chunk_id}
                className={`fusion-row${c.found_by_both ? ' is-both' : ''}`}
                role="row"
              >
                <span className="mono" role="cell">{label(c.chunk_index)}</span>
                <span className="tnum sub" role="cell">
                  {c.vector_rank ? `#${c.vector_rank}` : '-'}
                </span>
                <span className="tnum sub" role="cell">
                  {c.keyword_rank ? `#${c.keyword_rank}` : '-'}
                </span>
                <span className="stack" role="cell">
                  {/* 2px surface gap between the two fills, per mark spec. */}
                  <motion.span
                    className="stack-seg"
                    style={{ background: 'var(--vector)' }}
                    initial={{ width: 0 }}
                    whileInView={{ width: `${(c.vector_contribution / total) * 100}%` }}
                    viewport={{ once: true, amount: 0.5 }}
                    transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1], delay: i * 0.05 }}
                    title={`vector ${c.vector_contribution.toFixed(5)}`}
                  />
                  <motion.span
                    className="stack-seg"
                    style={{ background: 'var(--keyword)' }}
                    initial={{ width: 0 }}
                    whileInView={{ width: `${(c.keyword_contribution / total) * 100}%` }}
                    viewport={{ once: true, amount: 0.5 }}
                    transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1], delay: 0.06 + i * 0.05 }}
                    title={`keyword ${c.keyword_contribution.toFixed(5)}`}
                  />
                </span>
                <span className="tnum" role="cell">{c.score.toFixed(5)}</span>
              </div>
            )
          })}
        </div>
        <div className="legend">
          <span><i style={{ background: 'var(--vector)' }} /> Vector contribution</span>
          <span><i style={{ background: 'var(--keyword)' }} /> Keyword contribution</span>
        </div>
      </Scene>

      {/* ------------------------------------------------------------ 5 */}
      <Scene
        index={5}
        title="A slower, sharper model re-reads the survivors"
        lede={
          <>
            <p>
              Fusion still only knows about positions. A reranker actually reads the
              question together with each chunk and scores how well it answers it
              - far more accurate, and far too slow to run over the whole corpus.
            </p>
            <p>
              So it runs last, on{' '}
              <strong>{s.rerank.narrowed_from} candidates</strong>, keeping{' '}
              <strong>{s.rerank.narrowed_to}</strong>. What it discards matters as much
              as what it keeps.
            </p>
          </>
        }
        aside={
          <dl className="facts">
            <div><dt>Model</dt><dd className="mono">{s.rerank.model}</dd></div>
            <div><dt>Took</dt><dd className="tnum">{Math.round(result.timings.rerank)}ms</dd></div>
          </dl>
        }
      >
        <RankSlope data={slope} fromLabel="After fusion" toLabel="Final context" />
      </Scene>

      {/* ------------------------------------------------------------ 6 */}
      <Scene
        index={6}
        title="The prompt is just a string"
        lede={
          <>
            <p>
              Everything above exists to build this. The surviving{' '}
              {s.prompt.chunk_count} chunks are pasted into a template with the
              question, and that text is the <em>entire</em> universe the language
              model sees.
            </p>
            <p>
              It has no access to the source document, the database, or the rest of
              the corpus. If a fact didn&rsquo;t survive retrieval, it cannot appear in
              the answer.
            </p>
          </>
        }
        aside={
          s.prompt.token_count ? (
            <p className="muted">
              <span className="tnum">{s.prompt.token_count}</span> tokens sent to the
              model.
            </p>
          ) : null
        }
      >
        <pre className="prompt-view"><code>{s.prompt.text}</code></pre>
      </Scene>

      {/* ------------------------------------------------------------ 7 */}
      <Scene
        index={7}
        title="Then a second pass checks the answer"
        lede={
          <>
            <p>
              The model answers from that prompt. A separate call then re-reads the
              context and the answer together, looking for two failure modes: claims
              the context doesn&rsquo;t support, and information the answer says is
              missing when it is actually there.
            </p>
            <p>
              {s.retry.occurred
                ? 'This query failed that check, so the answer was regenerated with the problem described back to the model.'
                : 'This query passed, so the first answer was kept as-is.'}
            </p>
          </>
        }
      >
        <div className="verify-card">
          <div className="verify-head">
            <span className={`badge ${s.verify.grounded ? 'is-good' : 'is-bad'}`}>
              <span aria-hidden="true">{s.verify.grounded ? '✓' : '⚠'}</span>
              {s.verify.grounded ? 'Grounded' : 'Not grounded'}
            </span>
            <span className="mono sub">issue: {s.verify.issue}</span>
          </div>
          <p className="verify-reason">{s.verify.reasoning}</p>

          {s.retry.occurred ? (
            <div className="retry-diff">
              <div>
                <span className="label is-bad">First attempt - rejected</span>
                <p>{s.generate.answer}</p>
              </div>
              <div>
                <span className="label is-good">After regeneration</span>
                <p>{result.answer}</p>
              </div>
            </div>
          ) : (
            <div className="final-answer">
              <span className="label">Final answer</span>
              <p>{result.answer}</p>
            </div>
          )}
        </div>
      </Scene>

      {/* ------------------------------------------------------------ 8 */}
      <Scene
        index={8}
        title="Where the time actually went"
        lede={
          <>
            <p>
              All seven stages, measured. The shape is the point: everything on the
              retrieval side - embedding, both searches, fusion and reranking
              - accounts for{' '}
              <strong>{retrievalShare}%</strong> of the total.
            </p>
            <p>
              The two model calls dominate. Assembling the prompt is free - it
              is just string concatenation. That is why retrieval quality is worth
              optimising for accuracy rather than speed, and why the verification pass
              roughly doubles the wait.
            </p>
          </>
        }
        aside={
          <dl className="facts">
            <div><dt>Total</dt><dd className="tnum">{(result.timings.total / 1000).toFixed(2)}s</dd></div>
            <div><dt>Retrieval</dt><dd className="tnum">{Math.round(retrievalMs)}ms</dd></div>
            <div><dt>Model calls</dt><dd className="tnum">{Math.round(modelMs)}ms</dd></div>
          </dl>
        }
      >
        <div className="timings">
          {STAGE_ORDER.map((stage, i) => {
            const ms = result.timings[stage] ?? 0
            const isModel = stage === 'generate' || stage === 'verify'
            return (
              <div key={stage} className="timing-row">
                <span className="timing-label">{STAGE_LABELS[stage]}</span>
                <div className="timing-track">
                  <motion.div
                    className="timing-fill"
                    style={{ background: isModel ? 'var(--keyword)' : 'var(--vector)' }}
                    initial={{ width: 0 }}
                    whileInView={{ width: `${Math.max((ms / maxTiming) * 100, 0.8)}%` }}
                    viewport={{ once: true, amount: 0.4 }}
                    transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1], delay: i * 0.06 }}
                  />
                </div>
                <span className="timing-ms tnum">
                  {ms < 0.5 ? '<1ms' : `${Math.round(ms)}ms`}
                </span>
              </div>
            )
          })}
          {result.timings.retry ? (
            <p className="viz-note">
              Plus <span className="tnum">{Math.round(result.timings.retry)}ms</span>{' '}
              for the regeneration triggered by verification.
            </p>
          ) : null}
        </div>
        <div className="legend">
          <span><i style={{ background: 'var(--vector)' }} /> Retrieval</span>
          <span><i style={{ background: 'var(--keyword)' }} /> Model call</span>
        </div>
      </Scene>
    </div>
  )
}
