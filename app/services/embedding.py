import voyageai

EMBEDDING_MODEL = "voyage-4"
RERANK_MODEL = "rerank-2.5"

# The Voyage API accepts at most this many texts per embed request; the SDK
# declares it as voyageai.VOYAGE_EMBED_BATCH_SIZE but `client.embed` does not
# split for you -- it forwards the list whole. Sending more returns an API
# error, which previously surfaced as an unhandled 500 on any upload longer
# than ~128 chunks (roughly 25 pages).
EMBED_BATCH_SIZE = 128

client = voyageai.Client()


def embed_chunks(chunks: list[str]) -> list[list[float]]:
    """Embed every chunk, in batches the API will accept.

    Order is preserved: batches are concatenated in sequence, so the returned
    list lines up index-for-index with `chunks`.
    """
    embeddings: list[list[float]] = []
    for start in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[start : start + EMBED_BATCH_SIZE]
        result = client.embed(batch, model=EMBEDDING_MODEL, input_type="document")
        embeddings.extend(result.embeddings)
    return embeddings


def embed_question(question: str) -> list[float]:
    result = client.embed([question], model=EMBEDDING_MODEL, input_type="query")
    return result.embeddings[0]


def rerank_chunks(question: str, chunks: list[dict], top_k: int = 3) -> dict:
    """Rerank fused candidates, keeping both survivors and casualties.

    Returns {"kept": [...], "dropped": [...]}. What the reranker *discarded*
    is as informative as what it kept — it's the clearest evidence that
    retrieval order and relevance order are not the same thing.
    """
    if not chunks:
        return {"kept": [], "dropped": []}

    result = client.rerank(
        question, [c["text"] for c in chunks], model=RERANK_MODEL, top_k=top_k
    )

    kept = []
    kept_indices = set()
    for new_rank, r in enumerate(result.results, start=1):
        source = chunks[r.index]
        kept_indices.add(r.index)
        kept.append(
            {
                **source,
                "relevance_score": float(r.relevance_score),
                "rank": new_rank,
                "previous_rank": source.get("rank"),
                "rank_delta": (source.get("rank") or new_rank) - new_rank,
            }
        )

    dropped = [
        {**chunk, "relevance_score": None, "previous_rank": chunk.get("rank")}
        for index, chunk in enumerate(chunks)
        if index not in kept_indices
    ]

    return {"kept": kept, "dropped": dropped}


def project_to_2d(vectors: list[list[float]]) -> list[list[float]]:
    """Project high-dimensional embeddings to 2D with PCA, for display only.

    Uses the first two principal components of the supplied set, so coordinates
    are meaningful relative to each other within one query and are not
    comparable across queries.
    """
    import numpy as np

    if len(vectors) < 2:
        return [[0.0, 0.0] for _ in vectors]

    matrix = np.array(vectors, dtype=float)
    centered = matrix - matrix.mean(axis=0)
    # SVD is the numerically stable route to principal components and avoids
    # forming the covariance matrix explicitly.
    _, _, components = np.linalg.svd(centered, full_matrices=False)
    projected = centered @ components[:2].T

    # Normalise into roughly [-1, 1] so the frontend can scale to any viewport.
    largest = np.abs(projected).max()
    if largest > 0:
        projected = projected / largest

    return projected.tolist()
