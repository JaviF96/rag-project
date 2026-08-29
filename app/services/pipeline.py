from app.services.embedding import embed_question, rerank_chunks
from app.services.storage import search_similar_chunks, search_keyword_chunks, combine_with_rrf
from app.services.generation import build_prompt, call_claude
from app.services.verification import verify_answer

def run_pipeline(question: str) -> dict:
    question_embedding = embed_question(question)

    final_k = 3
    wide_k = final_k * 2

    top_chunks_vector = search_similar_chunks(question_embedding, top_k=wide_k)
    top_chunks_keyword = search_keyword_chunks(question, top_k=wide_k)
    fused_chunks = combine_with_rrf(top_chunks_vector, top_chunks_keyword, top_k=wide_k)
    reranked_chunks = rerank_chunks(question, fused_chunks, top_k=final_k)
    chunk_texts = [text for _, text in reranked_chunks]

    prompt = build_prompt(chunk_texts, question)
    first_answer = call_claude(prompt)

    verification = verify_answer(chunk_texts, first_answer)

    retried = False
    final_answer = first_answer
    if not verification["grounded"]:
        retried = True
        retry_prompt = prompt + f"\n\nNote: a previous attempt at this answer had an issue: {verification['reasoning']}. Re-examine the context carefully before answering again."
        final_answer = call_claude(retry_prompt)

    return {
        "answer": final_answer,
        "top_chunk_ids": [doc_id for doc_id, _ in reranked_chunks],
        "trace": {
            "vector_chunk_ids": [doc_id for doc_id, _ in top_chunks_vector],
            "keyword_chunk_ids": [doc_id for doc_id, _ in top_chunks_keyword],
            "fused_chunk_ids": [doc_id for doc_id, _ in fused_chunks],
            "reranked_chunk_ids": [doc_id for doc_id, _ in reranked_chunks],
            "first_answer": first_answer,
            "verification": verification,
            "retried": retried,
        }
    }