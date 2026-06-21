# backend/agents/graph/nodes.py
from backend.retrieval.sparse import sparse_search
from backend.retrieval.dense import dense_search
from backend.retrieval.hybrid import hybrid_search
from backend.retrieval.reranker import rerank
from backend.config.settings import settings
import logging

logger = logging.getLogger(__name__)


def retrieve_pdf_node(state):
    """
    Retrieve from PDF with adaptive granularity + cross-encoder reranking.
    Pipeline:
      1. Retrieve 3x candidates via sparse/dense/hybrid
      2. Zoom-out to macro if micro returns nothing
      3. Rerank with cross-encoder + jurisdiction boost -> keep top reranker_top_k
    """
    query       = state["query"]
    mode        = state["retrieval"]
    granularity = state.get("granularity", "micro")

    # Fetch more candidates for the reranker to choose from
    fetch_k = settings.default_k * 3

    # -- Select search strategy ------------------------------------------------
    if mode == "sparse":
        chunks = sparse_search(query, granularity=granularity, k=fetch_k)
    elif mode == "dense":
        chunks = dense_search(query, granularity=granularity, k=fetch_k)
    else:
        chunks = hybrid_search(query, granularity=granularity, k=fetch_k)

    # -- Adaptive fallback: zoom out to macro if micro is empty ----------------
    if len(chunks) == 0 and granularity == "micro":
        logger.warning("Micro-level retrieval returned 0 results -- zooming out to macro")
        if mode == "sparse":
            chunks = sparse_search(query, granularity="macro", k=fetch_k)
        elif mode == "dense":
            chunks = dense_search(query, granularity="macro", k=fetch_k)
        else:
            chunks = hybrid_search(query, granularity="macro", k=fetch_k)
        state["granularity"] = "macro"
        state["zoomed_out"]  = True

    # -- Cross-encoder reranking with jurisdiction authority boosting ----------
    if chunks:
        before = len(chunks)
        chunks = rerank(
            query,
            chunks,
            top_k=settings.reranker_top_k,
            jurisdiction_hint=state.get("detected_jurisdiction"),
        )
        logger.info(f"[reranker] {before} -> {len(chunks)} chunks after reranking")

    state["pdf_chunks"] = chunks
    return state
