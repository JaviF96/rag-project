import { useEffect, useRef, useState } from 'react'
import type { AskResponse } from '../api'

const SUGGESTIONS = [
  'Can someone on an active PIP be considered for a mid-year promotion?',
  'What does FTO stand for, and how many days does it give compared to the legacy plan?',
  'How many vacation days does someone hired in 2017 accrue?',
  'Is the Expense Review Committee involved in performance reviews?',
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

  useEffect(() => {
    if (mode === 'ask') inputRef.current?.focus()
  }, [mode])

  const submit = () => {
    if (question.trim() && !loading) onAsk(question.trim())
  }

  return (
    <header className={`hero${compact ? ' is-compact' : ''}`}>
      <div className="hero-inner">
        <p className="eyebrow">Retrieval-augmented generation</p>
        <h1 className="hero-title">
          Ask a question. Watch every step{' '}
          <br className="title-break" />
          the system takes to answer it.
        </h1>
        <p className="hero-sub">
          A working RAG pipeline over a PDF document. Ask it something, then open it
          up and see exactly how the answer was found.
        </p>

        {mode === 'idle' && !result ? (
          <div className="hero-actions">
            <button className="btn-primary" onClick={() => setMode('ask')}>
              Try a sample
            </button>
            <button className="btn-ghost" onClick={() => setMode('upload')}>
              Upload your own document
            </button>
          </div>
        ) : null}

        {mode === 'ask' && !result && !loading ? (
          <div className="ask-panel">
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
              <button className="btn-primary" onClick={submit} disabled={!question.trim()}>
                Run the pipeline
              </button>
            </div>

            {/* The sample prompts only make sense against the sample document. */}
            {!ownDocument ? (
              <>
                <p className="ask-hint">Or start from one of these:</p>
                <div className="suggestions">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      className="chip"
                      // Fills the input only -- running the pipeline stays an explicit
                      // action, since each run costs several model calls.
                      onClick={() => {
                        setQuestion(s)
                        inputRef.current?.focus()
                      }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
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
          </div>
        ) : null}

        {error ? (
          <p className="error" role="alert">
            {error}
          </p>
        ) : null}

        {result ? (
          <div className="answer-card">
            <p className="answer-question">{result.question}</p>
            <p className="answer-text">{result.answer}</p>
            <div className="answer-actions">
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
            </div>
          </div>
        ) : null}
      </div>
    </header>
  )
}
