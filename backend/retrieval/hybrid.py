from .dense import dense_search
from .sparse import sparse_search
from backend.config.settings import settings
from typing import List, Optional
from backend.ingestion.schemas import DocumentChunk
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)

# Shared thread pool — reused across all hybrid_search calls
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="retrieval")


def hybrid_search(
    query: str,
    granularity: str = "micro",
    k: int = None,
    # ── AML-specific filters ───────────────────────────────────────────────────
    index_type: Optional[str] = None,          # "regulatory" | "internal_policy"
    as_of_date: Optional[str] = None,          # ISO date "YYYY-MM-DD" — temporal filtering
    regulation_type: Optional[str] = None,     # "KYC" | "CTR" | "PEP" | etc.
    jurisdiction: Optional[str] = None,        # "RBI" | "FATF" | etc.
    document_tier: Optional[str] = None,       # "regulatory" | "internal_policy"
) -> List[DocumentChunk]:
    """
    Hybrid retrieval: dense + sparse run in PARALLEL, fused via Reciprocal Rank Fusion.
    ~40–50% faster than sequential execution.

    When index_type is set (e.g. "regulatory"), queries the dedicated AML collection
    instead of the generic micro/macro collections.

    AML filter parameters are passed through to ChromaStore.query() for metadata
    filtering and temporal (as_of_date) filtering.
    """
    k = k or settings.default_k
    fetch_k = k * 2   # fetch more candidates before fusion

    # Bundle AML kwargs to forward to dense/sparse
    aml_kwargs = dict(
        index_type=index_type,
        as_of_date=as_of_date,
        regulation_type=regulation_type,
        jurisdiction=jurisdiction,
        document_tier=document_tier,
    )

    # ── Run dense and sparse concurrently ─────────────────────────────────────
    futures = {
        _pool.submit(dense_search,  query, granularity, fetch_k, **aml_kwargs): "dense",
        _pool.submit(sparse_search, query, granularity, fetch_k, **aml_kwargs): "sparse",
    }

    dense_results: List[DocumentChunk] = []
    sparse_results: List[DocumentChunk] = []

    for future in as_completed(futures):
        label = futures[future]
        try:
            results = future.result()
            if label == "dense":
                dense_results = results
            else:
                sparse_results = results
        except Exception as exc:
            logger.warning(f"[hybrid_search] {label} search failed: {exc}")

    # ── Reciprocal Rank Fusion (RRF) ───────────────────────────────────────────
    rrf_scores: dict = {}

    for rank, chunk in enumerate(dense_results, 1):
        rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0) + 1 / (60 + rank)

    for rank, chunk in enumerate(sparse_results, 1):
        rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0) + 1 / (60 + rank)

    all_chunks = {chunk.id: chunk for chunk in dense_results + sparse_results}
    sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)

    result = [all_chunks[cid] for cid in sorted_ids[:k]]
    for chunk in result:
        chunk.score = rrf_scores[chunk.id]

    logger.debug(
        f"[hybrid] dense={len(dense_results)} sparse={len(sparse_results)} "
        f"fused→{len(result)} (granularity={granularity}, index_type={index_type})"
    )
    return result


