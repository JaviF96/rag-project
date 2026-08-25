import psycopg2
from pgvector.psycopg2 import register_vector
import os

def get_connection():
    conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
    cur = conn.cursor()
    cur.execute("SELECT * FROM pg_extension WHERE extname = 'vector';")
    print(cur.fetchall())
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