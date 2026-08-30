import { useCallback, useEffect, useRef, useState } from 'react'
import './app.css'
import { api, type AskResponse } from './api'
import { Hero, type Mode, type Source } from './components/Hero'
import { Walkthrough } from './components/Scenes'
import { Upload } from './components/Upload'

type Theme = 'light' | 'dark' | 'system'

function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      return (localStorage.getItem('rag-theme') as Theme) ?? 'system'
    } catch {
      return 'system'
    }
  })

  useEffect(() => {
    const root = document.documentElement
    if (theme === 'system') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', theme)
    try {
      localStorage.setItem('rag-theme', theme)
    } catch {
      /* storage blocked; the choice just won't persist */
    }
  }, [theme])

  return [theme, setTheme] as const
}

export default function App() {
  const [theme, setTheme] = useTheme()
  const [mode, setMode] = useState<Mode>('idle')
  const [result, setResult] = useState<AskResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Which document the questions target, and its name for the ask panel.
  const [source, setSource] = useState<Source>('demo')
  const [documentName, setDocumentName] = useState<string | null>(null)
  const [documentId, setDocumentId] = useState<string | null>(null)
  const [uploadedId, setUploadedId] = useState<string | null>(null)
  // Every metric in the app sits behind this gate.
  const [revealed, setRevealed] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => () => abortRef.current?.abort(), [])

  const ask = useCallback(async (question: string) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)
    setResult(null)
    setRevealed(false)
    try {
      setResult(await api.ask(question, documentId, controller.signal))
    } catch (e) {
      if ((e as Error)?.name === 'AbortError') return
      setError(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }, [documentId])

  /** Clear the answer and walkthrough so the ask panel can render again. */
  const askAnother = useCallback(() => {
    abortRef.current?.abort()
    setResult(null)
    setRevealed(false)
    setError(null)
    setMode('ask')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const reveal = useCallback(() => {
    setRevealed(true)
    // Wait a frame so the section exists before scrolling to it.
    requestAnimationFrame(() => {
      document.getElementById('walkthrough')?.scrollIntoView({
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
          ? 'auto'
          : 'smooth',
        block: 'start',
      })
    })
  }, [])

  const cycleTheme = () =>
    setTheme(theme === 'system' ? 'light' : theme === 'light' ? 'dark' : 'system')

  return (
    <>
      <button
        className="theme-toggle"
        onClick={cycleTheme}
        aria-label={`Theme: ${theme}. Click to change.`}
        title={`Theme: ${theme}`}
      >
        <span aria-hidden="true">
          {theme === 'light' ? '☀' : theme === 'dark' ? '☾' : '◐'}
        </span>
      </button>

      <Hero
        mode={mode}
        setMode={(m) => {
          if (m === 'ask' && mode === 'idle') {
            setSource('demo')
            setDocumentId(null)
          }
          setMode(m)
        }}
        source={source}
        documentName={documentName}
        onAsk={ask}
        loading={loading}
        result={result}
        error={error}
        onReveal={reveal}
        revealed={revealed}
        compact={mode === 'upload' || (!!result && revealed)}
        onAskAnother={askAnother}
        onUseDemo={() => {
          setSource('demo')
          setDocumentId(null)
        }}
        onUseOwn={() => {
          if (!uploadedId) return
          setSource('own')
          setDocumentId(uploadedId)
        }}
      />

      {loading ? (
        <div className="running" role="status">
          <span className="spinner" aria-hidden="true" />
          Working through the pipeline...
        </div>
      ) : null}

      {mode === 'upload' && !result && !loading ? (
        <Upload
          onIngested={(uploaded) => {
            setSource('own')
            setDocumentName(uploaded.filename)
            setDocumentId(uploaded.document_id)
            setUploadedId(uploaded.document_id)
            setMode('ask')
          }}
          onBack={() => {
            setSource('demo')
            setDocumentId(null)
            setMode('ask')
          }}
        />
      ) : null}

      {result && revealed ? <Walkthrough key={result.question} result={result} /> : null}
    </>
  )
}
