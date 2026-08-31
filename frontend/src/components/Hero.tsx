import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import type { AskResponse } from '../api'
import { spring, springSoft, useMotionSafe } from '../motion'

// Kept short enough to sit one line deep in a two-column grid. Each one still
// exercises a different part of the pipeline: date inference, an acronym only
// keyword search finds, a cross-section hop, and a claim the document never
// makes (which is what trips self-verification).
const SUGGESTIONS = [
  'How much time off does a 2017 hire accrue?',
  'How does FTO compare to the legacy PTO plan?',
  'Can someone on a PIP get a mid-year promotion?',
  'Does the Expense Review Committee run reviews?',
]

export type Mode = 'idle' | 'ask' | 'upload'
/** Which document the questions are aimed at. Drives the prompts and hints. */
export type Source = 'demo' | 'own'

/**
 * The landing surface. Deliberately holds almost nothing until the visitor
 * chooses a path: no metrics, no timings, no pipeline diagram. Everything
 * quantitative lives behind "See how it works".
 */
export function Hero({
  mode,
  setMode,
  source,
  documentName,
  onAsk,
  loading,
  result,
  error,
  onReveal,
  revealed,
  compact,
  onAskAnother,
  onUseDemo,
  onUseOwn,
}: {
  mode: Mode
  setMode: (m: Mode) => void
  source: Source
  documentName: string | null
  onAsk: (q: string) => void
  loading: boolean
  result: AskResponse | null
  error: string | null
  onReveal: () => void
  revealed: boolean
  /** True when a section follows the hero, so it shouldn't claim the viewport. */
  compact: boolean
  /** Clears the current answer and returns to the question input. */
  onAskAnother: () => void
  onUseDemo: () => void
  onUseOwn: () => void
}) {
  const [question, setQuestion] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const ownDocument = source === 'own'
  const { variants, stagger: staggerFor } = useMotionSafe()

  // One shared enter/exit for the mutually exclusive hero panels, so switching
  // between them reads as a single surface changing rather than a swap.
  const panel = {
    initial: { opacity: 0, y: 12 },
    animate: { opacity: 1, y: 0, transition: springSoft },
    exit: { opacity: 0, y: -8, transition: { duration: 0.18 } },
  }

  useEffect(() => {
    if (mode === 'ask') inputRef.current?.focus()
  }, [mode])

  const submit = () => {
    if (question.trim() && !loading) onAsk(question.trim())
  }

  return (
    <header className={`hero${compact ? ' is-compact' : ''}`}>
      <motion.div
        className="hero-inner"
        variants={staggerFor(0.08)}
        initial="hidden"
        animate="show"
      >
        <motion.p className="eyebrow" variants={variants}>
          Retrieval-augmented generation
        </motion.p>
        <motion.h1 className="hero-title" variants={variants}>
          Ask a question. Watch every step{' '}
          <br className="title-break" />
          the system takes to answer it.
        </motion.h1>
        <motion.p className="hero-sub" variants={variants}>
          A working RAG pipeline over a PDF document. Ask it something, then open it
          up and see exactly how the answer was found.
        </motion.p>

        <AnimatePresence mode="wait" initial={false}>
          {mode === 'idle' && !result ? (
            <motion.div className="hero-actions" key="actions" {...panel}>
              <button className="btn-primary" onClick={() => setMode('ask')}>
                Use the sample document
              </button>
              <button className="btn-ghost" onClick={() => setMode('upload')}>
                Upload your own document
              </button>
            </motion.div>
          ) : null}

          {mode === 'ask' && !result && !loading ? (
            <motion.div className="ask-panel" key="ask" {...panel}>
              {ownDocument && documentName ? (
                <p className="ask-target">
                  Asking about <strong>{documentName}</strong>
                </p>
              ) : null}

              <div className="ask">
                <input
                  ref={inputRef}
                  type="text"
                  value={question}
                  placeholder={
                    ownDocument
                      ? 'Ask something about your document...'
                      : 'Ask something about the sample document...'
                  }
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && submit()}
                  aria-label="Your question"
                />
                <button
                  className="btn-primary"
                  onClick={submit}
                  disabled={!question.trim()}
                >
                  Run the pipeline
                </button>
              </div>

              {/* The sample prompts only make sense against the sample document. */}
              {!ownDocument ? (
                <>
                  <p className="ask-hint">Or start from one of these:</p>
                  <motion.div
                    className="suggestions"
                    variants={staggerFor(0.045, 0.05)}
                    initial="hidden"
                    animate="show"
                  >
                    {SUGGESTIONS.map((s) => (
                      <motion.button
                        key={s}
                        className="chip"
                        variants={variants}
                        // Fills the input only -- running the pipeline stays an
                        // explicit action, since each run costs several model calls.
                        onClick={() => {
                          setQuestion(s)
                          inputRef.current?.focus()
                        }}
                      >
                        {s}
                      </motion.button>
                    ))}
                  </motion.div>
                </>
              ) : null}

              {/* An uploaded document stays ingested, so switching is two-way. */}
              <div className="ask-switch">
                {ownDocument ? (
                  <button className="link-back" onClick={onUseDemo}>
                    Or use the sample document instead
                  </button>
                ) : (
                  <>
                    {documentName ? (
                      <button className="link-back" onClick={onUseOwn}>
                        Or ask about {documentName} again
                      </button>
                    ) : null}
                    <button className="link-back" onClick={() => setMode('upload')}>
                      {documentName
                        ? 'Upload a different document'
                        : 'Or upload your own document instead'}
                    </button>
                  </>
                )}
              </div>
            </motion.div>
          ) : null}

          {result ? (
            <motion.div className="answer-card" key="answer" {...panel}>
              <p className="answer-question">{result.question}</p>
              <motion.p
                className="answer-text"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.12, duration: 0.45 }}
              >
                {result.answer}
              </motion.p>
              <motion.div
                className="answer-actions"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ ...spring, delay: 0.22 }}
              >
                {!revealed ? (
                  <button className="btn-primary btn-reveal" onClick={onReveal}>
                    See how it works <span aria-hidden="true">{'↓'}</span>
                  </button>
                ) : (
                  <a className="btn-ghost" href="#walkthrough">
                    Back to the walkthrough <span aria-hidden="true">{'↓'}</span>
                  </a>
                )}
                <button
                  className="link-back"
                  onClick={() => {
                    setQuestion('')
                    onAskAnother()
                  }}
                >
                  Ask another question
                </button>
              </motion.div>
            </motion.div>
          ) : null}
        </AnimatePresence>

        {error ? (
          <p className="error" role="alert">
            {error}
          </p>
        ) : null}
      </motion.div>
    </header>
  )
}
