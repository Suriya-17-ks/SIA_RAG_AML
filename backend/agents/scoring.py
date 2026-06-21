"""
Compliance Coverage Scoring
============================
Implements the mathematical coverage score formula from the research plan:

    CoverageScore_i = (0.7 × S_sim + 0.3 × S_cite) × W_reg

Where:
    S_sim  = cosine_similarity(obligation_embedding, best_policy_chunk_embedding) ∈ [0, 1]
    S_cite = citation_confidence (1.0 if evidence verified in retrieved chunk, else 0.0)
    W_reg  = regulatory_weight
                Mandatory   = 1.5
                Recommended = 1.0
                Optional    = 0.5

Overall score across N obligations:
    OverallCoverage = Σ(CoverageScore_i) / Σ(W_reg_i)   (weighted average)

This module is intentionally pure-Python / NumPy only — no LLM calls.
All components (S_sim, S_cite, W_reg) are stored on each GapResult so
the report generator can display fine-grained scores per gap.
"""
from __future__ import annotations

import numpy as np
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.agents.schemas.gap_schemas import GapResult

# ── Regulatory weight table ───────────────────────────────────────────────────
REGULATORY_WEIGHTS: dict[str, float] = {
    "Mandatory":   1.5,
    "Recommended": 1.0,
    "Optional":    0.5,
}
DEFAULT_WEIGHT = 1.0

# ── Score blend coefficients ──────────────────────────────────────────────────
W_SIM  = 0.7   # Weight for semantic similarity component
W_CITE = 0.3   # Weight for citation verification component


def get_regulatory_weight(obligation_level: Optional[str]) -> float:
    """
    Return the regulatory weight for a given obligation level.

    Args:
        obligation_level: "Mandatory" | "Recommended" | "Optional" | None

    Returns:
        Float weight (default 1.0 for unknown levels)
    """
    return REGULATORY_WEIGHTS.get(obligation_level or "", DEFAULT_WEIGHT)


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Compute cosine similarity between two embedding vectors.

    Returns:
        Float in [0, 1] — 0 = orthogonal, 1 = identical direction
    """
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.clip(np.dot(vec_a, vec_b) / (norm_a * norm_b), 0.0, 1.0))


def compute_coverage_score(
    s_sim: float,
    s_cite: float,
    obligation_level: Optional[str],
) -> tuple[float, float]:
    """
    Compute the coverage score for a single regulatory obligation.

    Formula:
        CoverageScore_i = (W_SIM × S_sim + W_CITE × S_cite) × W_reg

    Args:
        s_sim:            Cosine similarity between obligation & best policy chunk
        s_cite:           1.0 if evidence verified, 0.0 otherwise
        obligation_level: "Mandatory" | "Recommended" | "Optional"

    Returns:
        (coverage_score, w_reg) — both stored on GapResult for auditability
    """
    w_reg = get_regulatory_weight(obligation_level)
    raw   = W_SIM * s_sim + W_CITE * s_cite
    score = float(np.clip(raw * w_reg, 0.0, 1.5))   # max = 1.0 * 1.5 = 1.5
    return score, w_reg


def compute_overall_score(gap_results: "List[GapResult]") -> float:
    """
    Compute the overall weighted compliance coverage score.

    Formula:
        OverallCoverage = Σ(CoverageScore_i) / Σ(W_reg_i)

    Returns:
        Float in [0, 100] — percentage of weighted obligations covered
    """
    if not gap_results:
        return 0.0

    total_score  = sum(r.coverage_score for r in gap_results)
    total_weight = sum(r.w_reg for r in gap_results)

    if total_weight == 0:
        return 0.0

    # Normalise: max possible score if all obligations were COVERED is
    # Σ(W_SIM * 1.0 + W_CITE * 1.0) * W_reg_i = 1.0 * Σ(W_reg_i)
    normalised = (total_score / total_weight) * 100.0
    return float(np.clip(normalised, 0.0, 100.0))


def derive_severity(status: str, obligation_level: Optional[str]) -> str:
    """
    Derive a human-readable severity label from status and obligation level.

    Rules:
        MISSING  + Mandatory   → "critical"
        MISSING  + Recommended → "moderate"
        MISSING  + Optional    → "info"
        PARTIAL  + Mandatory   → "moderate"
        PARTIAL  + *           → "info"
        COVERED  + *           → "info"
    """
    if status == "MISSING":
        if obligation_level == "Mandatory":
            return "critical"
        elif obligation_level == "Recommended":
            return "moderate"
        return "info"
    elif status == "PARTIAL" and obligation_level == "Mandatory":
        return "moderate"
    return "info"


def enrich_gap_result(
    gap: "GapResult",
    obligation_embedding: Optional[np.ndarray],
    best_policy_embedding: Optional[np.ndarray],
    evidence_verified: bool,
) -> "GapResult":
    """
    Compute and populate all scoring fields on a GapResult in-place.

    Args:
        gap:                    GapResult with status and evidence already set
        obligation_embedding:   Dense embedding of the regulatory obligation text
        best_policy_embedding:  Dense embedding of the best-matching policy chunk
        evidence_verified:      True if LLM evidence string found in retrieved chunks

    Returns:
        The same gap object with s_sim, s_cite, w_reg, coverage_score, severity populated.
    """
    # S_sim — cosine similarity of embeddings
    if obligation_embedding is not None and best_policy_embedding is not None:
        gap.s_sim = cosine_similarity(obligation_embedding, best_policy_embedding)
    else:
        # Fallback: use status as proxy (COVERED=0.9, PARTIAL=0.5, MISSING=0.1)
        gap.s_sim = {"COVERED": 0.9, "PARTIAL": 0.5, "MISSING": 0.1}.get(gap.status, 0.3)

    # S_cite — citation verification
    gap.s_cite = 1.0 if (evidence_verified and gap.evidence) else 0.0
    gap.evidence_verified = evidence_verified

    # Coverage score + regulatory weight
    gap.coverage_score, gap.w_reg = compute_coverage_score(
        s_sim=gap.s_sim,
        s_cite=gap.s_cite,
        obligation_level=gap.obligation_level,
    )

    # Severity label
    gap.severity = derive_severity(gap.status, gap.obligation_level)

    return gap
