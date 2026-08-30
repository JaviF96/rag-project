-- Schema for the RAG chunk store.
--
-- Apply to a fresh database with:
--   psql "$DATABASE_URL" -f schema.sql
-- then seed the demo corpus with:
--   python -m seed.seed_demo_corpus

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id          SERIAL PRIMARY KEY,
    document_id TEXT NOT NULL,
    -- Ordinal of this chunk within its document, starting at 0. Stable across
    -- re-ingestion, unlike `id`, so the eval golden dataset can reference
    -- (document_id, chunk_index) instead of a global serial.
    chunk_index INTEGER NOT NULL,
    chunk_text  TEXT NOT NULL,
    -- 1024 dimensions = voyage-4 output. This must match the embedding model
    -- exactly; changing models means rebuilding the column.
    embedding   VECTOR(1024) NOT NULL,
    -- NULL marks the shared demo corpus, visible to everyone. A non-NULL value
    -- scopes the chunk to one browser session so uploads stay private to the
    -- visitor who made them.
    session_id  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Approximate nearest-neighbour index for the vector search. vector_l2_ops
-- matches the `<->` operator used in search_similar_chunks.
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_l2_ops);

-- Without this, the keyword search recomputes to_tsvector over every row on
-- every query.
CREATE INDEX IF NOT EXISTS chunks_text_fts
    ON chunks USING gin (to_tsvector('english', chunk_text));

-- Both searches filter on session visibility, so this is on the hot path.
CREATE INDEX IF NOT EXISTS chunks_session_id ON chunks (session_id);

CREATE INDEX IF NOT EXISTS chunks_document_id ON chunks (document_id);

-- Re-ingesting the same document should replace, not duplicate.
CREATE UNIQUE INDEX IF NOT EXISTS chunks_document_chunk
    ON chunks (document_id, chunk_index);
