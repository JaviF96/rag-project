from dotenv import load_dotenv

load_dotenv()

from fastapi import APIRouter, HTTPException, UploadFile, File
from app.services.extraction import extract_text_from_pdf
from app.services.chunking import chunk_text
from app.services.embedding import embed_chunks
from app.services.storage import save_chunks
from app.schemas import QuestionRequest
from app.services.generation import LLMError
from app.services.pipeline import run_pipeline

import uuid

router = APIRouter()

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


# Deliberately `def`, not `async def`: every call below (pypdf, voyageai, psycopg2,
# anthropic) is synchronous and blocking. In an `async def` handler they would block
# the event loop and serialise every other request behind them; in a plain `def`
# handler FastAPI runs them in its threadpool instead.
@router.post("/documents")
def upload_document(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=415,
            detail=f"Expected a PDF, got content type '{file.content_type}'.",
        )

    # Read one byte past the cap so an oversized file is detected without
    # pulling the whole thing into memory.
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.",
        )

    document_id = str(uuid.uuid4())

    try:
        text = extract_text_from_pdf(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read the PDF: {e}") from e

    if not text.strip():
        raise HTTPException(status_code=400, detail="No text found in the PDF document.")

    chunks = chunk_text(text)
    embeddings = embed_chunks(chunks)

    save_chunks(document_id, chunks, embeddings)

    return {"document_id": document_id, "chunks_created": len(chunks)}

@router.post("/ask")
def ask_question(request: QuestionRequest):
    try:
        return run_pipeline(request.question)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
