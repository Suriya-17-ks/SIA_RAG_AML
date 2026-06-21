from backend.storage.chroma_client import ChromaStore, get_aml_store
from backend.config.settings import settings
from typing import List, Optional
from backend.ingestion.schemas import DocumentChunk
from rank_bm25 import BM25Okapi


def sparse_search(
    query: str,
    granularity: str = "micro",
    k: int = None,
    # ── AML-specific filters ───────────────────────────────────────────────────
    index_type: Optional[str] = None,          # "regulatory" | "internal_policy"
    as_of_date: Optional[str] = None,          # ISO date "YYYY-MM-DD" — temporal filter
    regulation_type: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    document_tier: Optional[str] = None,
) -> List[DocumentChunk]:
    """
    Sparse (keyword-based) retrieval using BM25 algorithm.

    When index_type is set, fetches documents from the dedicated AML collection
    (aml_regulatory or aml_internal_policy) for BM25 scoring.
    Post-fetch, applies as_of_date temporal filtering consistent with dense retrieval.

    Returns:
        List of DocumentChunk objects sorted by BM25 score (descending)
    """
    k = k or settings.default_k

    if index_type in ("regulatory", "internal_policy"):
        store = get_aml_store(index_type)
    else:
        store = ChromaStore(granularity=granularity)

    # Fetch all documents from the collection for BM25 index
    all_results = store.collection.get()

    if not all_results or not all_results['documents']:
        return []

    # ── Tokenize documents for BM25 ────────────────────────────────────────────
    tokenized_docs = [doc.lower().split() for doc in all_results['documents']]
    bm25 = BM25Okapi(tokenized_docs)

    # Get BM25 scores for the query
    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)

    # Sort by score (descending), get top-k
    top_k_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k * 2]

    # ── Build DocumentChunk results with AML metadata ──────────────────────────
    chunks = []
    for idx in top_k_indices:
        if scores[idx] <= 0:
            continue   # Skip non-matching documents

        metadata = all_results['metadatas'][idx]

        # ── Temporal filter (consistent with dense retrieval) ─────────────────
        if as_of_date:
            eff = metadata.get("effective_date", "")
            if eff and eff > as_of_date:
                continue   # regulation not yet effective at as_of_date

        # ── Optional metadata pre-filter ──────────────────────────────────────
        if regulation_type and metadata.get("regulation_type") != regulation_type:
            continue
        if jurisdiction and metadata.get("jurisdiction") != jurisdiction:
            continue
        if document_tier and metadata.get("document_tier") != document_tier:
            continue

        chunks.append(DocumentChunk(
            id=all_results['ids'][idx],
            content=all_results['documents'][idx],
            doc_id=metadata.get('doc_id', ''),
            source=metadata.get('source', ''),
            page=metadata.get('page_number', 0),
            section_title=metadata.get('section_title') or None,
            content_type=metadata.get('content_type', 'paragraph'),
            score=float(scores[idx]),
            # AML metadata
            regulation_type=metadata.get('regulation_type') or None,
            obligation_level=metadata.get('obligation_level') or None,
            jurisdiction=metadata.get('jurisdiction') or None,
            document_tier=metadata.get('document_tier') or None,
            effective_date=metadata.get('effective_date') or None,
        ))

        if len(chunks) >= k:
            break

    return chunks


