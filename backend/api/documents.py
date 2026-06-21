# backend/api/documents.py
from fastapi import APIRouter, HTTPException
from backend.storage.chroma_client import ChromaStore
from typing import List
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/")
def list_documents():
    """
    List all unique documents indexed in ChromaDB (micro collection).
    Returns doc_id, source filename, and chunk count for each document.
    """
    try:
        store = ChromaStore(granularity="micro")
        docs = store.list_documents()
        return {"documents": docs, "total": len(docs)}
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{doc_id}")
def delete_document(doc_id: str):
    """
    Delete all chunks for a specific document from both micro and macro collections.
    """
    try:
        micro_store = ChromaStore(granularity="micro")
        macro_store = ChromaStore(granularity="macro")
        micro_store.delete_document(doc_id)
        macro_store.delete_document(doc_id)
        return {"status": "deleted", "doc_id": doc_id}
    except Exception as e:
        logger.error(f"Failed to delete document {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/")
def clear_database():
    """
    Clear the entire ChromaDB — deletes ALL documents from both collections.
    """
    try:
        micro_store = ChromaStore(granularity="micro")
        macro_store = ChromaStore(granularity="macro")
        micro_store.delete_collection()
        macro_store.delete_collection()
        return {"status": "cleared", "message": "All documents removed from both collections"}
    except Exception as e:
        logger.error(f"Failed to clear database: {e}")
        raise HTTPException(status_code=500, detail=str(e))
