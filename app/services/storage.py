import os
import threading
from contextlib import contextmanager

import psycopg2
from pgvector.psycopg2 import register_vector
from psycopg2 import pool as pg_pool

# Visibility rule shared by both searches: the demo corpus (session_id IS NULL)
# is visible to everyone, plus whatever the current session uploaded. Without
# this, one visitor's upload joins every other visitor's retrieval.
_VISIBLE = "(session_id IS NULL OR session_id = %s)"


def _scope(document_id: str | None) -> tuple[str, list]:
    """Visibility clause, optionally narrowed to a single document.

    The session check is always applied, even when a document_id is given -- so
    passing someone else's document_id matches nothing rather than leaking it.
    """
    if document_id:
        return f"{_VISIBLE} AND document_id = %s", [document_id]
    return _VISIBLE, []


# A single /ask previously opened three separate connections (vector search,
# keyword search, embedding fetch). Against a managed database each of those is
# a fresh TCP + TLS handshake on the request's critical path, and the pattern
# scales concurrency straight into the provider's connection cap. The pool is
# threaded because the FastAPI routes are sync `def`, so they run in the
# threadpool rather than on the event loop.
_pool: pg_pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> pg_pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                dsn = os.environ.get("DATABASE_URL")
                if not dsn:
                    raise RuntimeError("DATABASE_URL is not set.")
                _pool = pg_pool.ThreadedConnectionPool(
                    minconn=int(os.environ.get("DB_POOL_MIN", 1)),
                    maxconn=int(os.environ.get("DB_POOL_MAX", 10)),
                    dsn=dsn,
                )
    return _pool


@contextmanager
def get_connection():
    """Borrow a pooled connection, returning it even on failure.

    A connection that errored is discarded rather than returned to the pool, so
    a broken socket can't be handed to the next caller.
    """
    pool = _get_pool()
    conn = pool.getconn()
    try:
        register_vector(conn)
        yield conn
    except Exception:
        pool.putconn(conn, close=True)
        raise
    else:
        pool.putconn(conn)


def close_pool() -> None:
    """Release every pooled connection (called on application shutdown)."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


def check_connection() -> None:
    """Raise if the database is unreachable. Used by the readiness probe."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()


def save_chunks(
    document_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
    session_id: str | None = None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            for index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                cursor.execute(
                    """
                    INSERT INTO chunks (document_id, chunk_index, chunk_text, embedding, session_id)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (document_id, chunk_index) DO UPDATE
                        SET chunk_text = EXCLUDED.chunk_text,
                            embedding  = EXCLUDED.embedding
                    """,
                    (document_id, index, chunk, embedding, session_id),
                )
        conn.commit()


def search_similar_chunks(
    question_embedding: list[float],
    top_k: int = 6,
    session_id: str | None = None,
    document_id: str | None = None,
) -> list[dict]:
    """Nearest neighbours by L2 distance, with the distance kept.

    The distance is what makes the result explainable — returning bare IDs
    throws away the only evidence of *why* a chunk ranked where it did.
    """
    where, extra = _scope(document_id)
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id, document_id, chunk_index, chunk_text,
                       embedding <-> %s::vector AS distance
                FROM chunks
                WHERE {where}
                ORDER BY distance
                LIMIT %s
                """,
                [question_embedding, session_id, *extra, top_k],
            )
            rows = cursor.fetchall()

    return [
        {
            "chunk_id": cid,
            "document_id": doc_id,
            "chunk_index": idx,
            "text": text,
            "distance": float(distance),
            "rank": rank,
        }
        for rank, (cid, doc_id, idx, text, distance) in enumerate(rows, start=1)
    ]


def search_keyword_chunks(
    question: str,
    top_k: int = 6,
    session_id: str | None = None,
    document_id: str | None = None,
) -> list[dict]:
    """Full-text search, with the ts_rank score kept.

    plainto_tsquery ANDs every lexeme together, so a natural-language question
    of ten words requires a chunk containing all ten and reliably matches
    nothing. Rewriting the '&' operators to '|' gives OR semantics: a chunk
    matches on any term, and ts_rank sorts by how many and how densely. The
    rewrite goes through plainto_tsquery's own output, so the input is already
    sanitised of tsquery operators.
    """
    where, extra = _scope(document_id)
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                WITH q AS (
                    SELECT replace(plainto_tsquery('english', %s)::text, '&', '|')::tsquery AS query
                )
                SELECT id, document_id, chunk_index, chunk_text,
                       ts_rank(to_tsvector('english', chunk_text), q.query) AS score
                FROM chunks, q
                WHERE to_tsvector('english', chunk_text) @@ q.query
                  AND {where}
                ORDER BY score DESC
                LIMIT %s
                """,
                [question, session_id, *extra, top_k],
            )
            rows = cursor.fetchall()

    return [
        {
            "chunk_id": cid,
            "document_id": doc_id,
            "chunk_index": idx,
            "text": text,
            "score": float(score),
            "rank": rank,
        }
        for rank, (cid, doc_id, idx, text, score) in enumerate(rows, start=1)
    ]


def combine_with_rrf(
    vector_results: list[dict],
    keyword_results: list[dict],
    k: int = 60,
    top_k: int = 6,
) -> list[dict]:
    """Reciprocal Rank Fusion, returning the full working rather than just winners.

    Each entry records where the chunk placed in each list and what that
    contributed to its score, so the fusion arithmetic can be shown rather
    than asserted.
    """
    vector_ranks = {r["chunk_id"]: r["rank"] for r in vector_results}
    keyword_ranks = {r["chunk_id"]: r["rank"] for r in keyword_results}
    sources = {r["chunk_id"]: r for r in vector_results + keyword_results}

    fused = []
    for chunk_id in vector_ranks.keys() | keyword_ranks.keys():
        vector_rank = vector_ranks.get(chunk_id)
        keyword_rank = keyword_ranks.get(chunk_id)
        vector_contribution = 1 / (k + vector_rank) if vector_rank else 0.0
        keyword_contribution = 1 / (k + keyword_rank) if keyword_rank else 0.0
        source = sources[chunk_id]
        fused.append(
            {
                "chunk_id": chunk_id,
                "document_id": source["document_id"],
                "chunk_index": source["chunk_index"],
                "text": source["text"],
                "vector_rank": vector_rank,
                "keyword_rank": keyword_rank,
                "vector_contribution": vector_contribution,
                "keyword_contribution": keyword_contribution,
                "score": vector_contribution + keyword_contribution,
                "found_by_both": vector_rank is not None and keyword_rank is not None,
            }
        )

    fused.sort(key=lambda item: item["score"], reverse=True)
    for rank, item in enumerate(fused[:top_k], start=1):
        item["rank"] = rank

    return fused[:top_k]


def fetch_embeddings(chunk_ids: list[int]) -> dict[int, list[float]]:
    """Load raw embeddings for the given chunks, for the 2D projection."""
    if not chunk_ids:
        return {}

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, embedding FROM chunks WHERE id = ANY(%s)", (list(chunk_ids),)
            )
            rows = cursor.fetchall()

    # pgvector returns its own Vector type, not a plain sequence.
    return {
        cid: (embedding.to_list() if hasattr(embedding, "to_list") else list(embedding))
        for cid, embedding in rows
    }


def session_usage(session_id: str) -> dict:
    """How much this session has already stored.

    Used to enforce per-session ceilings so one visitor cannot fill the
    database, and so the cost of embedding is bounded per browser.
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(DISTINCT document_id), count(*)
                FROM chunks
                WHERE session_id = %s
                """,
                (session_id,),
            )
            documents, chunks = cursor.fetchone()

    return {"documents": documents or 0, "chunks": chunks or 0}


def delete_expired_sessions(ttl_days: int) -> int:
    """Drop session-scoped chunks older than the TTL. Returns rows removed.

    The demo corpus has session_id IS NULL and is never touched. Without this
    the table grows without bound, since nothing else ever deletes an upload.
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM chunks
                WHERE session_id IS NOT NULL
                  AND created_at < now() - make_interval(days => %s)
                """,
                (ttl_days,),
            )
            removed = cursor.rowcount
        conn.commit()

    return removed


def count_chunks(session_id: str | None = None) -> dict:
    """Corpus size, split into shared demo chunks and this session's uploads."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*) FILTER (WHERE session_id IS NULL),
                       count(*) FILTER (WHERE session_id = %s)
                FROM chunks
                """,
                (session_id,),
            )
            demo, session = cursor.fetchone()

    return {"demo_chunks": demo, "session_chunks": session}
