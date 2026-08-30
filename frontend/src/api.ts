const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

/** Stable per-browser id so uploads stay scoped to this visitor. */
export function sessionId(): string {
  const KEY = 'rag-inspector-session'
  try {
    let id = localStorage.getItem(KEY)
    if (!id) {
      id = crypto.randomUUID()
      localStorage.setItem(KEY, id)
    }
    return id
  } catch {
    // Private mode / blocked storage: fall back to a per-tab id.
    return 'ephemeral'
  }
}

export interface Chunk {
  chunk_id: number
  document_id: string
  chunk_index: number
  text: string
  rank?: number
}

export interface VectorChunk extends Chunk { distance: number }
export interface KeywordChunk extends Chunk { score: number }

export interface FusedChunk extends Chunk {
  vector_rank: number | null
  keyword_rank: number | null
  vector_contribution: number
  keyword_contribution: number
  score: number
  found_by_both: boolean
}

export interface RerankedChunk extends FusedChunk {
  relevance_score: number | null
  previous_rank: number | null
  rank_delta?: number
}

export interface Verification {
  grounded: boolean
  issue: string
  reasoning: string
}

export interface Stages {
  embed: {
    model: string
    dimensions: number
    preview: number[]
    projection: {
      question: [number, number]
      chunks: { chunk_id: number; x: number; y: number }[]
    }
  }
  vector_search: { candidates: VectorChunk[]; top_k: number }
  keyword_search: { candidates: KeywordChunk[]; top_k: number }
  fusion: { k: number; candidates: FusedChunk[] }
  rerank: {
    model: string
    kept: RerankedChunk[]
    dropped: RerankedChunk[]
    narrowed_from: number
    narrowed_to: number
  }
  prompt: { text: string; chunk_count: number; token_count: number | null }
  generate: { model: string; answer: string }
  verify: Verification
  retry: { occurred: boolean; note: string | null; final_answer: string | null }
}

export interface AskResponse {
  question: string
  answer: string
  top_chunk_ids: number[]
  top_chunk_indexes: number[]
  stages: Stages
  timings: Record<string, number>
}

export interface UploadResponse {
  document_id: string
  filename: string
  chunks_created: number
  word_count: number
  sample_chunks: { chunk_index: number; text: string }[]
}

export interface CorpusStatus {
  demo_chunks: number
  session_chunks: number
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'x-session-id': sessionId(), ...(init.headers ?? {}) },
  })
  if (!res.ok) {
    // FastAPI puts the useful message in `detail`; surface it rather than a bare status.
    let detail = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (body?.detail) detail = String(body.detail)
    } catch { /* non-JSON error body */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  /** documentId scopes retrieval to one document; omit it to search the demo corpus. */
  ask: (question: string, documentId?: string | null, signal?: AbortSignal) =>
    request<AskResponse>('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, document_id: documentId ?? null }),
      signal,
    }),

  upload: (file: File) => {
    const body = new FormData()
    body.append('file', file)
    return request<UploadResponse>('/documents', { method: 'POST', body })
  },

  corpus: () => request<CorpusStatus>('/corpus'),
}

export const STAGE_ORDER = [
  'embed',
  'vector_search',
  'keyword_search',
  'fusion',
  'rerank',
  'prompt',
  'generate',
  'verify',
] as const

export const STAGE_LABELS: Record<string, string> = {
  embed: 'Embed',
  vector_search: 'Vector',
  keyword_search: 'Keyword',
  fusion: 'Fuse',
  rerank: 'Rerank',
  prompt: 'Prompt',
  generate: 'Generate',
  verify: 'Verify',
  retry: 'Retry',
  total: 'Total',
}
