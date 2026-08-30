import { AnimatePresence, motion } from 'motion/react'
import { useRef, useState } from 'react'
import { api, type UploadResponse } from '../api'
import { springSoft, useMotionSafe } from '../motion'

/**
 * Ingestion panel. Uploads are scoped to this browser session, so a visitor's
 * document is retrievable by them and nobody else.
 *
 * Deliberately shows no counts or chunk previews once the upload lands -- that
 * is pipeline detail, and all of it belongs behind "See how it works".
 */
export function Upload({
  onIngested,
  onBack,
}: {
  onIngested: (result: UploadResponse) => void
  onBack: () => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<UploadResponse | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const upload = async () => {
    if (!file) return
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      setResult(await api.upload(file))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setBusy(false)
    }
  }

  const { reduced } = useMotionSafe()

  return (
    <section className="upload">
      <motion.div
        className="upload-inner"
        initial={reduced ? { opacity: 0 } : { opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={springSoft}
      >
        <h2>Use your own document</h2>
        <p className="upload-lede">
          Add a PDF and it goes through the same pipeline. It is scoped to your
          browser session &mdash; other visitors can&rsquo;t retrieve it.
        </p>

        <div className="upload-controls">
          <label className="file-label">
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null)
                setResult(null)
                setError(null)
              }}
            />
            <span>{file ? file.name : 'Choose a PDF...'}</span>
          </label>
          {!result ? (
            <button className="btn-primary" onClick={upload} disabled={!file || busy}>
              {busy ? 'Ingesting...' : 'Ingest'}
            </button>
          ) : null}
        </div>

        {error ? (
          <p className="error" role="alert">
            {error}
          </p>
        ) : null}

        <AnimatePresence mode="wait" initial={false}>
          {result ? (
            <motion.div
              className="upload-done"
              key="done"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={springSoft}
            >
              <button className="btn-primary" onClick={() => onIngested(result)}>
                Ask a question about it
              </button>
            </motion.div>
          ) : (
            <motion.button
              className="link-back"
              key="back"
              onClick={onBack}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              Or use the sample document instead
            </motion.button>
          )}
        </AnimatePresence>
      </motion.div>
    </section>
  )
}
