"""
Two-Stage Gap Detection Engine
================================
Compares an internal bank/NBFC AML policy document against all indexed
regulatory obligations and generates a structured GapReport.

Two-Stage Architecture (cost-optimised):
    Stage 1 — Free pre-filter:
        Use hybrid retrieval to find the top-N most relevant regulatory
        obligations for the given policy. No LLM calls.
        Reduces ~300 obligations → top 75.

    Stage 2 — LLM judge (top-N only):
        For each pre-filtered obligation, retrieve matching policy chunks
        and call the LLM to classify: COVERED | PARTIAL | MISSING.
        Structured JSON output, parsed via Pydantic.

    Stage 3 — Evidence guard:
        Verify that the LLM's evidence quote exists in the retrieved chunk
        text. Reject (mark unverified) if not found.

Cost reduction: ~70% fewer LLM calls vs naive "loop all obligations".
"""
from __future__ import annotations

import uuid
import time
import json
import logging
from typing import List, Optional
from datetime import datetime

import numpy as np

from backend.config.settings import settings, get_llm_client, get_model_name
from backend.retrieval.hybrid import hybrid_search
from backend.ingestion.schemas import DocumentChunk
from backend.agents.schemas.gap_schemas import (
    GapResult,
    GapReport,
    LLMJudgeOutput,
)
from backend.agents.scoring import enrich_gap_result, compute_overall_score

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
STAGE1_FETCH_K   = 120   # Stage 1: candidate pool from hybrid search
STAGE2_MAX_N     = 75    # Stage 2: max obligations to LLM-judge
POLICY_CONTEXT_K = 5     # Policy chunks retrieved per obligation in Stage 2
EVIDENCE_FUZZ_THRESHOLD = 75   # minimum fuzzy match ratio to verify evidence (0-100)


# ── LLM Judge Prompt ───────────────────────────────────────────────────────────
_JUDGE_PROMPT = """You are a senior AML compliance auditor for Indian banking.
Your task: determine if the internal AML policy satisfies a specific regulatory obligation.

Regulatory Obligation:
  Text: {obligation_text}
  Source: {regulation_source}, Page {regulation_page}
  Jurisdiction: {jurisdiction}
  Obligation Level: {obligation_level}
  Regulation Type: {regulation_type}

Internal Policy Text (relevant excerpts):
{policy_context}

Task: Does the internal policy adequately satisfy this regulatory obligation?

Rules:
- COVERED: Policy text directly and specifically addresses this obligation
- PARTIAL: Policy mentions the topic but lacks specifics (threshold, deadline, procedure, or scope)
- MISSING: No corresponding policy clause found — genuine compliance gap

Respond ONLY as valid JSON (no markdown):
{{
  "status": "COVERED" | "PARTIAL" | "MISSING",
  "evidence": "<direct verbatim quote from policy text above that proves coverage, or null if MISSING>",
  "gap_reason": "<if PARTIAL or MISSING: concise explanation of what is missing>",
  "confidence": <float 0.0-1.0 reflecting your certainty>,
  "remediation": "<if PARTIAL or MISSING: specific suggested policy clause to add or fix>"
}}"""


def _verify_evidence(evidence: Optional[str], chunks: List[DocumentChunk]) -> bool:
    """
    Evidence hallucination guard.
    Returns True if the LLM's claimed evidence quote can be found in
    at least one retrieved chunk (fuzzy substring match).
    """
    if not evidence or not chunks:
        return False

    try:
        from rapidfuzz import fuzz as rf_fuzz
        all_text = " ".join(c.content for c in chunks)
        ratio = rf_fuzz.partial_ratio(evidence[:200], all_text)
        return ratio >= EVIDENCE_FUZZ_THRESHOLD
    except ImportError:
        # Fallback: simple substring check on first 100 chars of evidence
        snippet = evidence[:100].lower().strip()
        all_text = " ".join(c.content for c in chunks).lower()
        return snippet in all_text


def _call_llm_judge(
    obligation: DocumentChunk,
    policy_chunks: List[DocumentChunk],
    llm_client,
    model_name: str,
) -> Optional[LLMJudgeOutput]:
    """
    Call the LLM to judge whether the policy covers the given obligation.
    Returns None if parsing fails (caller should mark as MISSING with low confidence).
    """
    # Build policy context string with inline citations
    context_blocks = []
    for i, chunk in enumerate(policy_chunks[:POLICY_CONTEXT_K], 1):
        citation = f"[Policy: {chunk.source}, Page {chunk.page}]"
        if chunk.section_title:
            citation += f" §{chunk.section_title}"
        context_blocks.append(f"Excerpt {i} {citation}:\n{chunk.content[:800]}")

    policy_context = "\n\n".join(context_blocks) or "(no matching policy text found)"

    prompt = _JUDGE_PROMPT.format(
        obligation_text   = obligation.content[:600],
        regulation_source = obligation.source,
        regulation_page   = obligation.page,
        jurisdiction      = obligation.jurisdiction or "Unknown",
        obligation_level  = obligation.obligation_level or "Mandatory",
        regulation_type   = obligation.regulation_type or "General",
        policy_context    = policy_context,
    )

    try:
        response = llm_client.chat_completion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0,       # deterministic for compliance judgments
        )
        raw = response.choices[0].message.content
        return LLMJudgeOutput.model_validate_json(raw)
    except Exception as exc:
        logger.warning(f"[gap_detector] LLM judge failed for {obligation.id}: {exc}")
        return None


class GapDetector:
    """
    Two-stage AML compliance gap detector.

    Usage:
        detector = GapDetector()
        report   = detector.analyze(policy_doc_id="uuid-...", as_of_date="2024-03-01")
    """

    def __init__(self):
        self._llm_client = None
        self._model_name: str = ""

    def _get_llm(self):
        if self._llm_client is None:
            self._llm_client = get_llm_client()
            self._model_name = get_model_name("verifier")
            logger.info(f"[gap_detector] LLM initialised: {self._model_name}")
        return self._llm_client

    # ── Stage 1: Hybrid pre-filter ──────────────────────────────────────────────
    def _stage1_prefilter(
        self,
        policy_doc_id: str,
        as_of_date: Optional[str],
        jurisdiction_filter: Optional[str],
        regulation_type_filter: Optional[str],
    ) -> List[DocumentChunk]:
        """
        Retrieve the most relevant regulatory obligations for the given policy
        using free hybrid search (no LLM). Reduces the obligation pool from
        hundreds to a manageable top-N before LLM judging.
        """
        # Retrieve a broad policy summary to use as the query
        policy_chunks = hybrid_search(
            query      = "AML compliance obligations KYC STR CTR PEP EDD reporting requirements",
            index_type = "internal_policy",
            k          = 10,
        )
        policy_text = " ".join(c.content[:200] for c in policy_chunks[:5]) if policy_chunks \
            else "AML compliance policy document"

        # Search regulatory corpus using policy text as query
        regulatory_obligations = hybrid_search(
            query            = policy_text,
            index_type       = "regulatory",
            k                = STAGE1_FETCH_K,
            as_of_date       = as_of_date,
            regulation_type  = regulation_type_filter,
            jurisdiction     = jurisdiction_filter,
        )

        logger.info(
            f"[gap_detector] Stage 1: retrieved {len(regulatory_obligations)} "
            f"regulatory obligations (cap={STAGE1_FETCH_K})"
        )
        return regulatory_obligations[:STAGE2_MAX_N]

    # ── Stage 2: LLM judge ──────────────────────────────────────────────────────
    def _stage2_judge(
        self,
        obligations: List[DocumentChunk],
    ) -> List[GapResult]:
        """
        For each regulatory obligation, retrieve matching policy chunks and
        ask the LLM to classify coverage. Applies evidence guard on each result.
        """
        llm = self._get_llm()
        results: List[GapResult] = []
        hallucination_rejections = 0

        for i, obligation in enumerate(obligations):
            logger.debug(f"[gap_detector] Judging {i+1}/{len(obligations)}: {obligation.id}")

            # Retrieve matching policy chunks
            policy_chunks = hybrid_search(
                query      = obligation.content,
                index_type = "internal_policy",
                k          = POLICY_CONTEXT_K,
            )

            # LLM judge
            judge_output = _call_llm_judge(obligation, policy_chunks, llm, self._model_name)

            if judge_output is None:
                # LLM failed — default to MISSING with low confidence
                judge_output = LLMJudgeOutput(
                    status="MISSING",
                    evidence=None,
                    gap_reason="LLM judgment unavailable — manual review required",
                    confidence=0.3,
                    remediation=None,
                )

            # Evidence guard
            evidence_verified = False
            if judge_output.status != "MISSING" and judge_output.evidence:
                evidence_verified = _verify_evidence(judge_output.evidence, policy_chunks)
                if not evidence_verified:
                    hallucination_rejections += 1
                    logger.warning(
                        f"[gap_detector] Evidence NOT verified for {obligation.id} "
                        f"— marking as UNVERIFIED"
                    )
                    # Downgrade to PARTIAL if evidence can't be confirmed
                    if judge_output.status == "COVERED":
                        judge_output.status = "PARTIAL"
                        judge_output.gap_reason = "Coverage claimed but evidence quote not verifiable in policy text."

            # Determine best policy chunk for embedding comparison
            best_policy_chunk = policy_chunks[0] if policy_chunks else None

            # Build GapResult
            gap = GapResult(
                obligation_id      = obligation.id,
                obligation_text    = obligation.content,
                regulation_source  = obligation.source,
                regulation_page    = obligation.page,
                regulation_section = obligation.section_title,
                jurisdiction       = obligation.jurisdiction,
                obligation_level   = obligation.obligation_level,
                regulation_type    = obligation.regulation_type,
                effective_date     = obligation.effective_date,
                status             = judge_output.status,
                severity           = "info",   # will be set by enrich_gap_result
                confidence         = judge_output.confidence,
                evidence           = judge_output.evidence if evidence_verified else None,
                evidence_source    = best_policy_chunk.source if best_policy_chunk else None,
                evidence_page      = best_policy_chunk.page if best_policy_chunk else None,
                gap_reason         = judge_output.gap_reason,
                remediation        = judge_output.remediation,
            )

            # Enrich with scoring (embeddings not available here — use proxy)
            gap = enrich_gap_result(
                gap                   = gap,
                obligation_embedding  = None,   # proxy scoring used
                best_policy_embedding = None,
                evidence_verified     = evidence_verified,
            )

            results.append(gap)

        logger.info(
            f"[gap_detector] Stage 2 complete: {len(results)} results, "
            f"{hallucination_rejections} hallucination rejections"
        )
        self._hallucination_rejections = hallucination_rejections
        return results

    # ── Public API ──────────────────────────────────────────────────────────────
    def analyze(
        self,
        policy_doc_id: str,
        as_of_date: Optional[str] = None,
        jurisdiction_filter: Optional[str] = None,
        regulation_type_filter: Optional[str] = None,
        max_obligations: int = STAGE2_MAX_N,
    ) -> GapReport:
        """
        Run the full two-stage gap analysis.

        Args:
            policy_doc_id:          UUID of the ingested internal policy document
            as_of_date:             ISO date — only regulations effective on/before this date
            jurisdiction_filter:    Restrict to one jurisdiction (e.g. "RBI")
            regulation_type_filter: Restrict to one AML type (e.g. "KYC")
            max_obligations:        Cap on Stage 2 LLM calls (default: 75)

        Returns:
            GapReport with full gap analysis, scores, and evidence citations
        """
        self._hallucination_rejections = 0
        t_start = time.time()

        logger.info(
            f"[gap_detector] Starting analysis for policy={policy_doc_id} "
            f"as_of_date={as_of_date} jurisdiction={jurisdiction_filter}"
        )

        # Stage 1: pre-filter
        obligations = self._stage1_prefilter(
            policy_doc_id          = policy_doc_id,
            as_of_date             = as_of_date,
            jurisdiction_filter    = jurisdiction_filter,
            regulation_type_filter = regulation_type_filter,
        )
        stage1_count = len(obligations)

        # Respect the caller's cap
        obligations = obligations[:max_obligations]

        # Stage 2: LLM judge
        gap_results = self._stage2_judge(obligations)

        # Separate by status
        covered = [r for r in gap_results if r.status == "COVERED"]
        partial = [r for r in gap_results if r.status == "PARTIAL"]
        missing = [r for r in gap_results if r.status == "MISSING"]

        # Sort missing by severity (critical first)
        severity_order = {"critical": 0, "moderate": 1, "info": 2}
        missing.sort(key=lambda r: severity_order.get(r.severity, 2))
        partial.sort(key=lambda r: severity_order.get(r.severity, 2))

        # Overall score
        overall_score = compute_overall_score(gap_results)

        # Average confidence
        avg_conf = (
            sum(r.confidence for r in gap_results) / len(gap_results)
            if gap_results else 0.0
        )

        latency = time.time() - t_start

        report = GapReport(
            report_id                  = str(uuid.uuid4()),
            policy_doc_id              = policy_doc_id,
            policy_source              = "internal_policy",
            assessment_date            = datetime.now().isoformat(),
            as_of_date                 = as_of_date,
            regulatory_frameworks      = [],   # populated by report_generator
            total_obligations_analyzed = len(gap_results),
            overall_coverage_score     = round(overall_score, 2),
            summary = {
                "covered": len(covered),
                "partial": len(partial),
                "missing": len(missing),
            },
            missing                    = missing,
            partial                    = partial,
            covered                    = covered,
            stage1_obligations_retrieved = stage1_count,
            stage2_obligations_analyzed  = len(gap_results),
            hallucination_rejections     = self._hallucination_rejections,
            avg_confidence               = round(avg_conf, 3),
            latency_seconds              = round(latency, 2),
        )

        logger.info(
            f"[gap_detector] Analysis complete in {latency:.1f}s — "
            f"score={overall_score:.1f}% covered={len(covered)} "
            f"partial={len(partial)} missing={len(missing)}"
        )
        return report
