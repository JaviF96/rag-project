from dotenv import load_dotenv 
load_dotenv()  

from fastapi import APIRouter, HTTPException, UploadFile, File
from app.services.extraction import extract_text_from_pdf
from app.services.chunking import chunk_text
from app.services.embedding import embed_chunks
from app.services.embedding import embed_question
from app.services.storage import save_chunks
from app.services.storage import search_similar_chunks
from app.schemas import QuestionRequest
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
    top_chunks = search_similar_chunks(question_embedding)
    return {"top_chunks": top_chunks}