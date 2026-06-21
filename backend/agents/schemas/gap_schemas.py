"""
Gap Detection Pydantic Schemas
==============================
All data models for the two-stage gap detection pipeline,
compliance scoring, and structured report output.
"""
from __future__ import annotations

from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from typing_extensions import Literal
from datetime import datetime


# ── Individual gap result ──────────────────────────────────────────────────────

class GapResult(BaseModel):
    """
    Represents the compliance status of a single regulatory obligation
    against the internal policy document.
    """
    # ── Obligation identity ────────────────────────────────────────────────────
    obligation_id: str                          # chunk_id from aml_regulatory collection
    obligation_text: str                        # Full regulatory clause text
    regulation_source: str                      # e.g. "RBI-KYC-Master-Direction-2023"
    regulation_page: int                        # Page number in source document
    regulation_section: Optional[str] = None   # Section title if available
    jurisdiction: Optional[str] = None         # RBI | FATF | FIU-IND | etc.
    obligation_level: Optional[str] = None     # Mandatory | Recommended | Optional
    regulation_type: Optional[str] = None      # KYC | CTR | PEP | etc.
    effective_date: Optional[str] = None       # ISO date string

    # ── Gap detection result ───────────────────────────────────────────────────
    status: Literal["COVERED", "PARTIAL", "MISSING"]
    severity: Literal["critical", "moderate", "info"]  # derived from status + obligation_level
    confidence: float = Field(ge=0.0, le=1.0)          # LLM confidence in its own judgment

    # ── Evidence ──────────────────────────────────────────────────────────────
    evidence: Optional[str] = None             # Direct quote from policy proving coverage
    evidence_source: Optional[str] = None      # Policy source doc name
    evidence_page: Optional[int] = None        # Page in policy where evidence was found
    gap_reason: Optional[str] = None           # Explanation for PARTIAL or MISSING

    # ── Scoring components (from scoring.py) ──────────────────────────────────
    s_sim: float = 0.0                         # Cosine similarity between obligation & policy embeddings
    s_cite: float = 0.0                        # Citation confidence (1.0 if evidence verified, else 0.0)
    w_reg: float = 1.0                         # Regulatory weight (Mandatory=1.5, Recommended=1.0, Optional=0.5)
    coverage_score: float = 0.0               # Final: (0.7*s_sim + 0.3*s_cite) * w_reg

    # ── Remediation ───────────────────────────────────────────────────────────
    remediation: Optional[str] = None          # LLM-suggested policy language to fix the gap

    # ── Graph traceability ────────────────────────────────────────────────────
    graph_path: Optional[str] = None           # e.g. "FATF-R10 → PMLA-S12 → RBI-KYC-4 → [MISSING]"

    # ── Hallucination guard ───────────────────────────────────────────────────
    evidence_verified: bool = True             # False if evidence string not found in retrieved chunks


class GapReport(BaseModel):
    """
    Full compliance gap analysis report for one internal policy document
    against the indexed regulatory corpus.
    """
    # ── Report identity ────────────────────────────────────────────────────────
    report_id: str
    policy_doc_id: str
    policy_source: str                          # Policy filename
    assessment_date: str                        # ISO datetime of this analysis run
    as_of_date: Optional[str] = None           # Temporal filter applied (if any)
    regulatory_frameworks: List[str] = []      # e.g. ["FATF-40R-2023", "RBI-KYC-MD-2023"]

    # ── Aggregate statistics ───────────────────────────────────────────────────
    total_obligations_analyzed: int
    overall_coverage_score: float              # Weighted average of all CoverageScore_i
    summary: Dict[str, int] = {}              # {"covered": N, "partial": N, "missing": N}

    # ── Detailed gap lists ─────────────────────────────────────────────────────
    missing: List[GapResult] = []             # 🔴 Critical — no corresponding policy clause
    partial: List[GapResult] = []             # 🟡 Partial — mentioned but incomplete
    covered: List[GapResult] = []             # 🟢 Covered — full alignment found

    # ── Processing metadata ────────────────────────────────────────────────────
    stage1_obligations_retrieved: int = 0     # After hybrid pre-filter (Stage 1)
    stage2_obligations_analyzed: int = 0     # After LLM judge (Stage 2)
    hallucination_rejections: int = 0        # LLM outputs rejected by evidence guard
    avg_confidence: float = 0.0              # Average LLM confidence across all results
    latency_seconds: float = 0.0            # Total wall-clock time for analysis
    estimated_token_cost_usd: float = 0.0   # Approximate cost of LLM calls


# ── LLM judge intermediate output (internal use) ──────────────────────────────

class LLMJudgeOutput(BaseModel):
    """
    Structured output from the LLM judge prompt.
    Parsed from JSON response before evidence verification.
    """
    status: Literal["COVERED", "PARTIAL", "MISSING"]
    evidence: Optional[str] = None
    gap_reason: Optional[str] = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    remediation: Optional[str] = None


# ── API request/response models ────────────────────────────────────────────────

class GapAnalysisRequest(BaseModel):
    """FastAPI request body for /gap-analysis/ endpoint."""
    policy_doc_id: Optional[str] = None        # If already ingested
    as_of_date: Optional[str] = None           # ISO date "YYYY-MM-DD"
    jurisdiction_filter: Optional[str] = None  # Restrict to one jurisdiction
    regulation_type_filter: Optional[str] = None  # Restrict to one AML type
    max_obligations: int = Field(default=75, ge=10, le=300)  # Stage 2 cap
    tag_mode: str = "hybrid"


class GapAnalysisResponse(BaseModel):
    """FastAPI response from /gap-analysis/ endpoint."""
    report: GapReport
    message: str = "Gap analysis complete"
    markdown: Optional[str] = None   # Rendered Markdown narrative report
