"""Load the demo corpus into the shared (session_id IS NULL) scope.

    python -m seed.seed_demo_corpus

Idempotent: re-running replaces the demo document's chunks rather than
duplicating them. Embeddings are recomputed at seed time so the JSON file
stays readable and editable.
"""

from dotenv import load_dotenv 

load_dotenv()

import json
import os
from pathlib import Path

from app.services.embedding import embed_chunks
from app.services.storage import close_pool, get_connection

# Fixed id so re-seeding is idempotent and the eval golden dataset can
# reference this document by name.
DEMO_DOCUMENT_ID = "demo-meridian-handbook"

CORPUS_PATH = Path(__file__).parent / "demo_corpus.json"


def seed() -> int:
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    chunks = corpus["chunks"]

    print(f"Embedding {len(chunks)} chunks from {corpus['title']}...")
    embeddings = embed_chunks(chunks)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM chunks WHERE document_id = %s", (DEMO_DOCUMENT_ID,))
            for index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                cursor.execute(
                    """
                    INSERT INTO chunks (document_id, chunk_index, chunk_text, embedding, session_id)
                    VALUES (%s, %s, %s, %s, NULL)
                    """,
                    (DEMO_DOCUMENT_ID, index, chunk, embedding),
                )
        conn.commit()

    return len(chunks)


if __name__ == "__main__":
    try:
        count = seed()
    finally:
        # Release pooled connections so the script exits promptly.
        close_pool()
    print(f"Seeded {count} chunks as document '{DEMO_DOCUMENT_ID}' (shared corpus).")
