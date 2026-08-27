from dotenv import load_dotenv
load_dotenv()

from app.services.embedding import embed_question, rerank_chunks
from app.services.storage import search_similar_chunks, search_keyword_chunks, combine_with_rrf
from app.services.generation import build_prompt, call_claude

def run_pipeline(question: str) -> dict:
    question_embedding = embed_question(question)

    final_k = 3
    wide_k = final_k * 2

    top_chunks_vector = search_similar_chunks(question_embedding, top_k=wide_k)
    top_chunks_keyword = search_keyword_chunks(question, top_k=wide_k)
    fused_chunks = combine_with_rrf(top_chunks_vector, top_chunks_keyword, top_k=wide_k)

    reranked_chunks = rerank_chunks(question, fused_chunks, top_k=final_k)

    prompt = build_prompt([text for _, text in reranked_chunks], question)
    answer = call_claude(prompt)
    
    return {
        "answer": answer,
        "top_chunk_ids": [doc_id for doc_id, _ in reranked_chunks]
    }
