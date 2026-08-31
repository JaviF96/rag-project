from dotenv import load_dotenv

load_dotenv()

import logging
import uuid

import psycopg2
from fastapi import APIRouter, File, Header, HTTPException, Request, UploadFile

from app import config
from app.limiter import limiter
from app.schemas import QuestionRequest
from app.services.chunking import chunk_text, estimate_chunk_count
from app.services.embedding import embed_chunks
from app.services.extraction import extract_text_from_pdf
from app.services.generation import LLMError
from app.services.pipeline import run_pipeline
from app.services.storage import save_chunks, session_usage

log = logging.getLogger("rag.routes")

router = APIRouter()


def valid_session_id(x_session_id: str | None) -> str | None:
    """Accept only a UUID as the session id.

    The header is client-supplied and is written straight into the database, so
    it needs a bound on both shape and length. Anything malformed is treated as
    "no session", which limits the caller to the shared demo corpus rather than
    failing the request.
    """
    if not x_session_id:
        return None
    try:
        return str(uuid.UUID(x_session_id))
    except (ValueError, AttributeError, TypeError):
        log.warning("Rejected malformed session id (%d chars)", len(x_session_id or ""))
        return None


# Deliberately `def`, not `async def`: every call below (pypdf, voyageai, psycopg2,
# anthropic) is synchronous and blocking. In an `async def` handler they would block
# the event loop and serialise every other request behind them; in a plain `def`
# handler FastAPI runs them in its threadpool instead.
@router.post("/documents")
@limiter.limit(config.UPLOAD_RATE_LIMIT)
def upload_document(
    request: Request,
    file: UploadFile = File(...),
    x_session_id: str | None = Header(default=None),
):
    session_id = valid_session_id(x_session_id)
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="A valid x-session-id header (UUID) is required to upload.",
        )

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=415,
            detail=f"Expected a PDF, got content type '{file.content_type}'.",
        )

    # Read one byte past the cap so an oversized file is detected without
    # pulling the whole thing into memory.
    content = file.file.read(config.MAX_UPLOAD_BYTES + 1)
    if len(content) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.",
        )

    try:
        text = extract_text_from_pdf(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read the PDF: {e}") from e

    if not text.strip():
        raise HTTPException(status_code=400, detail="No text found in the PDF document.")

    # Both ceilings are checked before embedding, so a rejected document costs
    # nothing in API spend.
    chunk_count = estimate_chunk_count(text)
    if chunk_count > config.MAX_CHUNKS_PER_DOCUMENT:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Document is too long: about {chunk_count} chunks, "
                f"limit is {config.MAX_CHUNKS_PER_DOCUMENT}."
            ),
        )

    try:
        usage = session_usage(session_id)
    except psycopg2.Error as e:
        log.exception("Database unavailable during upload")
        raise HTTPException(status_code=503, detail="Storage is unavailable.") from e

    if usage["documents"] >= config.MAX_DOCUMENTS_PER_SESSION:
        raise HTTPException(
            status_code=429,
            detail=(
                f"You have reached the limit of {config.MAX_DOCUMENTS_PER_SESSION} "
                "documents for this session."
            ),
        )
    if usage["chunks"] + chunk_count > config.MAX_CHUNKS_PER_SESSION:
        raise HTTPException(
            status_code=429,
            detail="This document would exceed the storage limit for your session.",
        )

    document_id = str(uuid.uuid4())
    chunks = chunk_text(text)

    try:
        embeddings = embed_chunks(chunks)
    except Exception as e:
        # Previously unhandled: any embedding failure surfaced as a bare 500.
        log.exception("Embedding failed for %s (%d chunks)", file.filename, len(chunks))
        raise HTTPException(
            status_code=502, detail="Could not embed the document; try again shortly."
        ) from e

    try:
        save_chunks(document_id, chunks, embeddings, session_id=session_id)
    except psycopg2.Error as e:
        log.exception("Failed to store chunks for %s", document_id)
        raise HTTPException(status_code=503, detail="Storage is unavailable.") from e

    log.info(
        "Ingested %s: %d chunks for session %s", file.filename, len(chunks), session_id[:8]
    )
    return {
        "document_id": document_id,
        "filename": file.filename,
        "chunks_created": len(chunks),
    }


@router.post("/ask")
@limiter.limit(config.ASK_RATE_LIMIT)
def ask_question(
    request: Request,
    payload: QuestionRequest,
    x_session_id: str | None = Header(default=None),
):
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    try:
        return run_pipeline(
            payload.question,
            session_id=valid_session_id(x_session_id),
            document_id=payload.document_id,
        )
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except psycopg2.Error as e:
        log.exception("Database unavailable during /ask")
        raise HTTPException(status_code=503, detail="Storage is unavailable.") from e
