from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from backend.ingestion.ingest_pipeline import ingest_pdf, ingest_regulatory_pdf, ingest_policy_pdf
from backend.ingestion.pdf_parser import get_converter
from typing import Optional
import asyncio
import os
import tempfile
import logging
import time

router = APIRouter()
logger = logging.getLogger(__name__)

# Thread-pool shared across all upload requests so embeddings and Docling
# run in worker threads rather than blocking the asyncio event loop.
_executor = None  # lazily created (default ThreadPoolExecutor)


@router.on_event("startup")
async def warmup():
    """
    Pre-load the Docling DocumentConverter in a thread on server startup
    so the FIRST real upload is fast (no 30-second model-load delay).
    """
    logger.info("Warming up DocumentConverter in background thread…")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_executor, get_converter)
    logger.info("DocumentConverter warm-up complete.")


@router.post("/")
async def upload_pdf(
    file: UploadFile = File(...),
    doc_type: Optional[str] = Form(default="general"),
    jurisdiction: Optional[str] = Form(default=None),
):
    """
    Upload and ingest a PDF file.

    doc_type options:
      - "regulatory"      → goes into aml_regulatory collection (used by gap analyzer Stage 1)
      - "internal_policy" → goes into aml_internal_policy collection (used by gap analyzer Stage 2)
      - "general"         → goes into generic documents_sentences collection (used by chat Q&A)

    jurisdiction: Optional override (e.g. "RBI", "FATF", "PMLA") for regulatory docs.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    contents = await file.read()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(contents)
        temp_path = tmp.name

    try:
        t0 = time.perf_counter()
        loop = asyncio.get_event_loop()

        doc_type = (doc_type or "general").strip().lower()

        if doc_type == "regulatory":
            doc_id = await loop.run_in_executor(
                _executor,
                lambda: ingest_regulatory_pdf(
                    temp_path,
                    doc_name=file.filename,
                    jurisdiction=jurisdiction or None,
                    tag_mode="hybrid",
                )
            )
            collection = "aml_regulatory"

        elif doc_type == "internal_policy":
            doc_id = await loop.run_in_executor(
                _executor,
                lambda: ingest_policy_pdf(
                    temp_path,
                    doc_name=file.filename,
                    tag_mode="hybrid",
                )
            )
            collection = "aml_internal_policy"

        else:  # "general" — original behaviour for chat Q&A
            doc_id = await loop.run_in_executor(
                _executor,
                lambda: ingest_pdf(temp_path, doc_name=file.filename)
            )
            collection = "documents_sentences + documents_sections"

        elapsed = round(time.perf_counter() - t0, 1)
        logger.info(
            f"Ingested '{file.filename}' as [{doc_type}] in {elapsed}s  "
            f"doc_id={doc_id}  collection={collection}"
        )

        return {
            "filename":   file.filename,
            "doc_id":     doc_id,
            "doc_type":   doc_type,
            "collection": collection,
            "status":     "success",
            "elapsed_s":  elapsed,
            "message":    f"PDF ingested as [{doc_type}] into {collection} in {elapsed}s",
        }

    except Exception as e:
        logger.exception(f"Ingestion failed for '{file.filename}'")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
