from time import perf_counter

from app.services.embedding import (
    EMBEDDING_MODEL,
    RERANK_MODEL,
    embed_question,
    project_to_2d,
    rerank_chunks,
)
from app.services.generation import (
    MODEL,
    build_prompt,
    call_claude,
    call_claude_detailed,
)
from app.services.storage import (
    combine_with_rrf,
    fetch_embeddings,
    search_keyword_chunks,
    search_similar_chunks,
)
from app.services.verification import verify_answer

FINAL_K = 3
WIDE_K = FINAL_K * 2
RRF_K = 60


class _Timer:
    """Collects wall-clock timings per stage, in milliseconds."""

    def __init__(self):
        self.timings: dict[str, float] = {}

    def time(self, name: str, fn, *args, **kwargs):
        start = perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            self.timings[name] = round((perf_counter() - start) * 1000, 1)


def _projection(question_embedding, candidates) -> dict:
    """2D PCA coordinates for the question and each candidate chunk."""
    chunk_ids = [c["chunk_id"] for c in candidates]
    embeddings = fetch_embeddings(chunk_ids)
    ordered = [(cid, embeddings[cid]) for cid in chunk_ids if cid in embeddings]
    if not ordered:
        return {"question": [0.0, 0.0], "chunks": []}

    points = project_to_2d([question_embedding] + [vec for _, vec in ordered])
    return {
        "question": points[0],
        "chunks": [
            {"chunk_id": cid, "x": point[0], "y": point[1]}
            for (cid, _), point in zip(ordered, points[1:])
        ],
    }


def run_pipeline(
    question: str, session_id: str | None = None, document_id: str | None = None
) -> dict:
    timer = _Timer()
    started = perf_counter()

    question_embedding = timer.time("embed", embed_question, question)

    vector_results = timer.time(
        "vector_search", search_similar_chunks, question_embedding, WIDE_K, session_id, document_id
    )
    keyword_results = timer.time(
        "keyword_search", search_keyword_chunks, question, WIDE_K, session_id, document_id
    )
    fused = timer.time(
        "fusion", combine_with_rrf, vector_results, keyword_results, RRF_K, WIDE_K
    )
    reranked = timer.time("rerank", rerank_chunks, question, fused, FINAL_K)

    kept = reranked["kept"]
    chunk_texts = [c["text"] for c in kept]

    prompt = timer.time("prompt", build_prompt, chunk_texts, question)
    generated = timer.time("generate", call_claude_detailed, prompt)
    first_answer = generated["text"]
    verification = timer.time("verify", verify_answer, chunk_texts, first_answer)

    retried = False
    final_answer = first_answer
    retry_note = None
    if not verification["grounded"]:
        retried = True
        retry_note = (
            f"Note: a previous attempt at this answer had an issue: "
            f"{verification['reasoning']}. Re-examine the context carefully before answering again."
        )
        final_answer = timer.time("retry", call_claude, f"{prompt}\n\n{retry_note}")

    timer.timings["total"] = round((perf_counter() - started) * 1000, 1)

    return {
        "question": question,
        "answer": final_answer,
        # Kept flat for the eval harness, which scores retrieval on these.
        "top_chunk_ids": [c["chunk_id"] for c in kept],
        "top_chunk_indexes": [c["chunk_index"] for c in kept],
        "stages": {
            "embed": {
                "model": EMBEDDING_MODEL,
                "dimensions": len(question_embedding),
                # A short slice is enough to make "text became numbers" concrete;
                # sending all 1024 floats would bloat every response.
                "preview": [round(v, 4) for v in question_embedding[:48]],
                "projection": _projection(question_embedding, fused),
            },
            "vector_search": {"candidates": vector_results, "top_k": WIDE_K},
            "keyword_search": {"candidates": keyword_results, "top_k": WIDE_K},
            "fusion": {"k": RRF_K, "candidates": fused},
            "rerank": {
                "model": RERANK_MODEL,
                "kept": kept,
                "dropped": reranked["dropped"],
                "narrowed_from": len(fused),
                "narrowed_to": len(kept),
            },
            "prompt": {
                "text": prompt,
                "chunk_count": len(chunk_texts),
                "token_count": generated["input_tokens"],
            },
            "generate": {
                "model": MODEL,
                "answer": first_answer,
                "output_tokens": generated["output_tokens"],
            },
            "verify": verification,
            "retry": {
                "occurred": retried,
                "note": retry_note,
                "final_answer": final_answer if retried else None,
            },
        },
        "timings": timer.timings,
    }
