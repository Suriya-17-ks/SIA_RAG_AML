"""
Cross-Encoder Reranker with Jurisdiction Authority Weighting
─────────────────────────────────────────────────────────────
Pipeline:
  1. Cross-encoder scores each (query, chunk) pair for semantic relevance.
  2. A jurisdiction authority weight is computed based on whether the query
     is India-specific and what jurisdiction the chunk belongs to.
  3. Final score = (semantic_score × 0.8) + (jurisdiction_weight × 0.2)

Jurisdiction hierarchy for India-specific queries:
  national (PMLA / RBI / FIU-IND / SEBI)   → weight 1.0
  regulatory direction (state-level / IRDAI) → weight 0.9
  international standard (FATF / EU / USA)   → weight 0.6

For cross-jurisdiction or non-India queries: all weights = 0.8 (neutral).

Model: cross-encoder/ms-marco-MiniLM-L-6-v2
  • 23M params, fast on GPU
  • ~20–60ms latency for 30 candidates
"""

from __future__ import annotations
import re
import logging
from typing import List, Optional, TYPE_CHECKING

from backend.config.settings import settings
from backend.ingestion.schemas import DocumentChunk

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

# ── Singleton cross-encoder ────────────────────────────────────────────────────
_cross_encoder: "CrossEncoder | None" = None


def _get_cross_encoder() -> "CrossEncoder":
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder  # lazy import
        device = settings.embedding_device
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        logger.info(
            f"Loading cross-encoder '{settings.reranker_model}' on device='{device}' …"
        )
        _cross_encoder = CrossEncoder(settings.reranker_model, device=device)
        logger.info("Cross-encoder ready.")
    return _cross_encoder


# ── Jurisdiction detection ─────────────────────────────────────────────────────

# Signals that the query is about Indian law specifically
_INDIA_SIGNALS = re.compile(
    r"₹|rupee|lakh|crore|"
    r"\bpmla\b|\brbi\b|\bfiu\b|\bfiu-ind\b|\bsebi\b|"
    r"\bindian?\b|\bindia\b|"
    r"\bprevention of money launder|\bmaster direction",
    re.IGNORECASE,
)

# Signals that the query is explicitly about international/FATF standards
_FATF_SIGNALS = re.compile(
    r"\bfatf\b|\bfinancial action task force\b|\b6amld\b|\beu directive\b|"
    r"\bglobal standard\b|\binternational standard\b",
    re.IGNORECASE,
)

# Signals for cross-jurisdiction comparison
_CROSS_SIGNALS = re.compile(
    r"\bcompare\b|\bvs\b|\bversus\b|\bdiffer\b|\bdifference\b|"
    r"\bacross jurisdiction\b|\bcross.jurisdiction\b",
    re.IGNORECASE,
)


def _detect_query_jurisdiction(query: str) -> Optional[str]:
    """
    Heuristic jurisdiction detection from the query text.
    Returns: "india" | "fatf" | "cross" | None
    """
    if _CROSS_SIGNALS.search(query):
        return "cross"
    if _INDIA_SIGNALS.search(query):
        return "india"
    if _FATF_SIGNALS.search(query):
        return "fatf"
    return None


# ── Jurisdiction authority weights ─────────────────────────────────────────────

#: National Indian regulators
_INDIA_NATIONAL = {"pmla", "rbi", "fiu-ind", "fiu_ind", "fiu", "sebi", "irdai"}
#: International / foreign standards
_INTERNATIONAL = {"fatf", "eu", "6amld", "usa", "bsa", "amld", "global"}


def _jurisdiction_weight(chunk: DocumentChunk, query_jurisdiction: Optional[str]) -> float:
    """
    Return a normalised authority weight [0.0, 1.0] for the chunk given the
    detected query jurisdiction.

    When query_jurisdiction is None, "cross", or "fatf" we return a neutral
    weight (0.8) so scoring is purely semantic — no distortion.
    """
    if query_jurisdiction != "india":
        return 0.8  # neutral — let semantic score decide

    chunk_jur = (getattr(chunk, "jurisdiction", "") or "").lower().strip()
    chunk_jur = chunk_jur.replace(" ", "_")

    if any(nat in chunk_jur for nat in _INDIA_NATIONAL):
        return 1.0   # national legislation — highest authority
    if any(intl in chunk_jur for intl in _INTERNATIONAL):
        return 0.6   # international standard — deprioritise for India queries
    return 0.8       # unknown / untagged — neutral


# ── Public API ─────────────────────────────────────────────────────────────────

def rerank(
    query: str,
    chunks: List[DocumentChunk],
    top_k: int | None = None,
    jurisdiction_hint: Optional[str] = None,
) -> List[DocumentChunk]:
    """
    Re-score `chunks` against `query` using the cross-encoder, then blend with
    jurisdiction authority weights.

    Final score = (semantic_score × 0.8) + (jurisdiction_weight × 0.2)

    Falls back to original order if the cross-encoder is unavailable or
    if `chunks` is empty / reranker is disabled in settings.

    Args:
        query:             The user's query string.
        chunks:            Candidate chunks from hybrid/dense/sparse retrieval.
        top_k:             Number of chunks to return (default: settings.reranker_top_k).
        jurisdiction_hint: Pre-detected jurisdiction from the router.
                           If None, we auto-detect from the query text.
    """
    if not settings.reranker_enabled or not chunks:
        return chunks[:top_k] if top_k else chunks

    top_k = top_k or settings.reranker_top_k

    # Resolve jurisdiction: prefer explicit hint from router, else auto-detect
    query_jurisdiction = jurisdiction_hint or _detect_query_jurisdiction(query)

    if query_jurisdiction:
        logger.info(f"[reranker] Jurisdiction detected: '{query_jurisdiction}'")

    try:
        encoder = _get_cross_encoder()
        pairs   = [(query, c.content) for c in chunks]
        raw_scores = encoder.predict(pairs)  # numpy array, one score per pair

        # Normalise semantic scores to [0, 1] using min-max over this batch
        s_min, s_max = float(raw_scores.min()), float(raw_scores.max())
        s_range = s_max - s_min if s_max > s_min else 1.0

        for chunk, raw in zip(chunks, raw_scores):
            sem  = (float(raw) - s_min) / s_range          # normalised semantic score
            jur  = _jurisdiction_weight(chunk, query_jurisdiction)  # authority weight
            chunk.score = (sem * 0.8) + (jur * 0.2)        # blended final score

        reranked = sorted(chunks, key=lambda c: c.score, reverse=True)[:top_k]

        logger.info(
            f"[reranker] {len(chunks)} → {len(reranked)} chunks "
            f"(top blended={reranked[0].score:.3f}, jurisdiction='{query_jurisdiction}')"
        )
        return reranked

    except Exception as exc:
        logger.warning(f"[reranker] Failed, falling back to original order: {exc}")
        return chunks[:top_k]
