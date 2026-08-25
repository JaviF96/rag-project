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


def search_similar_chunks(question_embedding: list[float], top_k: int = 3) -> list[str]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT chunk_text FROM chunks ORDER BY embedding <-> %s::vector LIMIT %s",
        (question_embedding, top_k)
    )

    results = cursor.fetchall()
    cursor.close()
    conn.close()

    return [row[0] for row in results]