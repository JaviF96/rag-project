from dotenv import load_dotenv

load_dotenv()  

from fastapi import APIRouter, HTTPException, UploadFile, File
from app.services.extraction import extract_text_from_pdf
from app.services.chunking import chunk_text
from app.services.embedding import embed_chunks, embed_question, rerank_chunks
from app.services.storage import combine_with_rrf, save_chunks, search_similar_chunks, search_keyword_chunks
from app.schemas import QuestionRequest
from app.services.generation import build_prompt, call_claude
from app.services.verification import verify_answer 

import uuid

router = APIRouter()

@router.post("/documents")
async def upload_document(file: UploadFile = File(...)):
    document_id = str(uuid.uuid4())
    content = await file.read()
    text = extract_text_from_pdf(content)

    if not text.strip():
        raise HTTPException(status_code=400, detail="No text found in the PDF document.")

    chunks = chunk_text(text)
    embeddings = embed_chunks(chunks)

    save_chunks(document_id, chunks, embeddings)

    return {"preview": text[:100], "chunks_preview": chunks[:3], "document_id": document_id, "embeddings_preview": len(embeddings[0])} 

    
@router.post("/ask")
def ask_question(request: QuestionRequest):
    question_embedding = embed_question(request.question)

    final_k = 3
    wide_k = final_k * 2

    top_chunks_vector = search_similar_chunks(question_embedding, top_k=wide_k)
    top_chunks_keyword = search_keyword_chunks(request.question, top_k=wide_k)
    fused_chunks = combine_with_rrf(top_chunks_vector, top_chunks_keyword, top_k=wide_k)

    reranked_chunks = rerank_chunks(request.question, fused_chunks, top_k=final_k)

    prompt = build_prompt([text for _, text in reranked_chunks], request.question)
    answer = call_claude(prompt)

    verification = verify_answer([text for _, text in reranked_chunks], answer)

    if not verification["grounded"]:
        retry_prompt = prompt + f"\n\n Note: A previous attempt at this answer had an issue: {verification['reasoning']}. Re examine the context carefully before trying again."
        answer = call_claude(retry_prompt)

    return {"answer": answer, "top_chunks": [text for _, text in reranked_chunks], "top_chunk_ids": [doc_id for doc_id, _ in reranked_chunks]}