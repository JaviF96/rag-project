import psycopg2
from pgvector.psycopg2 import register_vector
import os

def get_connection():
    conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
    register_vector(conn)
    return conn

def save_chunks(document_id: str, chunks: list[str], embeddings: list[list[float]]):
    conn = get_connection() 
    cursor = conn.cursor()

    for chunk, embedding in zip(chunks, embeddings):
        cursor.execute(
            "INSERT INTO chunks (document_id, chunk_text, embedding) VALUES (%s, %s, %s)",
            (document_id, chunk, embedding)
        )

    conn.commit() 
    cursor.close()
    conn.close()


def search_similar_chunks(question_embedding: list[float], top_k: int = 6) -> list[tuple[str, str]]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, chunk_text FROM chunks ORDER BY embedding <-> %s::vector LIMIT %s",
        (question_embedding, top_k)
    )

    results = cursor.fetchall()
    cursor.close()
    conn.close()

    return results

def search_keyword_chunks(question:str, top_k:int=6) -> list[tuple[str, str]]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, chunk_text FROM chunks
        WHERE to_tsvector('english', chunk_text) @@ plainto_tsquery('english', %s)
        ORDER BY ts_rank(to_tsvector('english', chunk_text), plainto_tsquery('english', %s)) DESC
        LIMIT %s
        """,
        (question, question, top_k)
    )

    results = cursor.fetchall()
    cursor.close()
    conn.close()

    return results


def combine_with_rrf(vector_results: list[tuple], keyword_results: list[tuple], k: int = 60, top_k: int = 6) -> list[str]:
    vector_ranks = {doc_id: rank for rank, (doc_id, _) in enumerate(vector_results, start=1)}
    keyword_ranks = {doc_id: rank for rank, (doc_id, _) in enumerate(keyword_results, start=1)}

    chunk_texts = {doc_id: chunk_text for doc_id, chunk_text in vector_results + keyword_results}

    unique_chunk_ids = set(vector_ranks.keys()) | set(keyword_ranks.keys())

    rrf_scores = {}
    for doc_id in unique_chunk_ids:
        score = 0
        if doc_id in vector_ranks:
            score += 1 / (k + vector_ranks[doc_id])
        if doc_id in keyword_ranks:
            score += 1 / (k + keyword_ranks[doc_id])
        rrf_scores[doc_id] = score

    sorted_chunks = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)

    top_chunks = [chunk_texts[doc_id] for doc_id, _ in sorted_chunks[:top_k]]

    return top_chunks
