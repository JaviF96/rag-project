import { useState } from 'react'

const API_BASE = 'http://localhost:8000'

interface Verification {
  grounded: boolean
  issue: string
  reasoning: string
}

interface Trace {
  vector_chunk_ids: number[]
  keyword_chunk_ids: number[]
  fused_chunk_ids: number[]
  reranked_chunk_ids: number[]
  first_answer: string
  verification: Verification
  retried: boolean
}

interface AskResponse {
  answer: string
  top_chunk_ids: number[]
  trace: Trace
}

function App() {
  const [file, setFile] = useState<File | null>(null)
  const [uploadStatus, setUploadStatus] = useState('')
  const [uploading, setUploading] = useState(false)

  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [result, setResult] = useState<AskResponse | null>(null)
  const [showTrace, setShowTrace] = useState(false)
  const [error, setError] = useState('')

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setUploadStatus('')
    setError('')

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch(`${API_BASE}/documents`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
      const data = await res.json()
      setUploadStatus(`Uploaded — ${data.chunks_created} chunks created.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleAsk = async () => {
    if (!question.trim()) return
    setAsking(true)
    setError('')
    setResult(null)

    try {
      const res = await fetch(`${API_BASE}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      if (!res.ok) throw new Error(`Request failed: ${res.status}`)
      const data: AskResponse = await res.json()
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setAsking(false)
    }
  }

  return (
    <div style={{ maxWidth: 700, margin: '0 auto', padding: 24, fontFamily: 'sans-serif' }}>
      <h1>RAG Handbook Q&A</h1>

      <section style={{ marginBottom: 32 }}>
        <h2>1. Upload a document</h2>
        <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <button onClick={handleUpload} disabled={!file || uploading}>
          {uploading ? 'Uploading...' : 'Upload'}
        </button>
        {uploadStatus && <p>{uploadStatus}</p>}
      </section>

      <section style={{ marginBottom: 32 }}>
        <h2>2. Ask a question</h2>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask something about the document..."
          style={{ width: '100%', padding: 8 }}
        />
        <button onClick={handleAsk} disabled={!question.trim() || asking}>
          {asking ? 'Thinking...' : 'Ask'}
        </button>
      </section>

      {error && <p style={{ color: 'red' }}>{error}</p>}

      {result && (
        <section>
          <h2>Answer</h2>
          <p>{result.answer}</p>

          <div style={{ marginTop: 16 }}>
            <span style={{
              padding: '4px 10px',
              borderRadius: 4,
              background: result.trace.verification.grounded ? '#d4f8d4' : '#f8d4d4',
              fontSize: 14,
            }}>
              {result.trace.verification.grounded ? '✓ Verified grounded' : '⚠ Flagged by verification'}
            </span>
            {result.trace.retried && (
              <span style={{ marginLeft: 8, fontSize: 14, color: '#666' }}>
                (regenerated after verification flagged an issue)
              </span>
            )}
          </div>

          <button onClick={() => setShowTrace(!showTrace)} style={{ marginTop: 16 }}>
            {showTrace ? 'Hide' : 'Show'} retrieval trace
          </button>

          {showTrace && (
            <div style={{ marginTop: 16, background: '#f5f5f5', padding: 16, borderRadius: 8 }}>
              <p><strong>Vector search chunk ids:</strong> {result.trace.vector_chunk_ids.join(', ') || '(none)'}</p>
              <p><strong>Keyword search chunk ids:</strong> {result.trace.keyword_chunk_ids.join(', ') || '(none)'}</p>
              <p><strong>Fused (RRF) chunk ids:</strong> {result.trace.fused_chunk_ids.join(', ')}</p>
              <p><strong>Reranked (final) chunk ids:</strong> {result.trace.reranked_chunk_ids.join(', ')}</p>
              <p><strong>Verification issue:</strong> {result.trace.verification.issue}</p>
              <p><strong>Verification reasoning:</strong> {result.trace.verification.reasoning}</p>
              {result.trace.retried && (
                <>
                  <p><strong>First attempt (before retry):</strong></p>
                  <p style={{ fontStyle: 'italic' }}>{result.trace.first_answer}</p>
                </>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  )
}

export default App