from backend.storage.chroma_client import ChromaStore, get_aml_store
from backend.config.settings import settings
from typing import List, Optional
from backend.ingestion.schemas import DocumentChunk


def dense_search(
    query: str,
    granularity: str = "micro",
    k: int = None,
    # ── AML-specific filters ───────────────────────────────────────────────────
    index_type: Optional[str] = None,          # "regulatory" | "internal_policy"
    as_of_date: Optional[str] = None,          # ISO date "YYYY-MM-DD"
    regulation_type: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    document_tier: Optional[str] = None,
) -> List[DocumentChunk]:
    """
    Dense (semantic) retrieval using vector similarity.

    When index_type is set, queries the dedicated AML collection (aml_regulatory or
    aml_internal_policy) instead of the generic micro/macro collections.
    """
    k = k or settings.default_k

    if index_type in ("regulatory", "internal_policy"):
        store = get_aml_store(index_type)
    else:
        store = ChromaStore(granularity=granularity)

    results = store.query(
        query_text=query,
        k=k,
        as_of_date=as_of_date,
        regulation_type=regulation_type,
        jurisdiction=jurisdiction,
        document_tier=document_tier,
    )
    return results

