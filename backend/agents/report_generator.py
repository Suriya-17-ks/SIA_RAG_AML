# -*- coding: utf-8 -*-
"""
AML Compliance Report Generator
================================
Transforms a raw GapReport into:
  1. A structured JSON dict (matching the spec in the research plan)
  2. A Markdown narrative report ready for PDF export / paper appendix

Usage:
    from backend.agents.report_generator import generate_report, render_markdown

    report_dict = generate_report(gap_report)
    md_text     = render_markdown(gap_report)
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.agents.schemas.gap_schemas import GapReport, GapResult

# ── Regulatory framework detection ─────────────────────────────────────────────
_FRAMEWORK_MAP = {
    "FATF":     "FATF-40R-2023",
    "RBI":      "RBI-KYC-MD-2023",
    "PMLA":     "PMLA-2002-Amd2023",
    "FIU-IND":  "FIU-IND-Guidelines-2023",
    "SEBI":     "SEBI-AML-Circular-2023",
}

_STATUS_ICON = {
    "COVERED": "🟢",
    "PARTIAL": "🟡",
    "MISSING": "🔴",
}

_SEVERITY_ICON = {
    "critical": "🚨",
    "moderate": "⚠️",
    "info":     "ℹ️",
}


def _detect_frameworks(gap_report: "GapReport") -> List[str]:
    """Extract which regulatory frameworks appear in the analyzed obligations."""
    seen = set()
    all_results = gap_report.covered + gap_report.partial + gap_report.missing
    for gap in all_results:
        j = gap.jurisdiction or ""
        if j in _FRAMEWORK_MAP and j not in seen:
            seen.add(j)
    # Always sort for deterministic output
    return [_FRAMEWORK_MAP[j] for j in sorted(seen) if j in _FRAMEWORK_MAP]


def _gap_to_dict(gap: "GapResult") -> dict:
    """Serialize a single GapResult to the spec JSON shape."""
    return {
        "obligation_id":    gap.obligation_id,
        "regulation_type":  gap.regulation_type,
        "jurisdiction":     gap.jurisdiction,
        "obligation_level": gap.obligation_level,
        "text":             gap.obligation_text,
        "source":           gap.regulation_source,
        "page":             gap.regulation_page,
        "section":          gap.regulation_section,
        "effective_date":   str(gap.effective_date) if gap.effective_date else None,
        "status":           gap.status,
        "severity":         gap.severity,
        "coverage_score":   round(gap.coverage_score, 4),
        "s_sim":            round(gap.s_sim, 4),
        "s_cite":           round(gap.s_cite, 4),
        "w_reg":            round(gap.w_reg, 4),
        "confidence":       round(gap.confidence, 3),
        "evidence":         gap.evidence,
        "evidence_verified":gap.evidence_verified,
        "evidence_source":  gap.evidence_source,
        "evidence_page":    gap.evidence_page,
        "gap_reason":       gap.gap_reason,
        "remediation":      gap.remediation,
        "graph_path":       gap.graph_path,
    }


def generate_report(gap_report: "GapReport") -> dict:
    """
    Produce the full structured JSON report from a GapReport.

    Returns:
        dict matching the research-spec JSON schema, including all gaps
        split by status, aggregate scores, and traceability paths.
    """
    frameworks = _detect_frameworks(gap_report)

    critical_gaps = [g for g in gap_report.missing if g.severity == "critical"]
    moderate_gaps = [g for g in gap_report.missing if g.severity == "moderate"] + \
                    [g for g in gap_report.partial  if g.severity == "moderate"]
    info_gaps     = [g for g in gap_report.missing if g.severity == "info"] + \
                    [g for g in gap_report.partial  if g.severity == "info"]

    report = {
        "report_id":                   gap_report.report_id,
        "assessment_date":             gap_report.assessment_date,
        "as_of_date":                  gap_report.as_of_date or str(date.today()),
        "regulatory_frameworks":       frameworks or gap_report.regulatory_frameworks,
        "overall_coverage_score":      gap_report.overall_coverage_score,
        "total_obligations_analyzed":  gap_report.total_obligations_analyzed,
        "summary": {
            "covered":  gap_report.summary.get("covered", 0),
            "partial":  gap_report.summary.get("partial", 0),
            "missing":  gap_report.summary.get("missing", 0),
        },
        "statistics": {
            "stage1_obligations_retrieved": gap_report.stage1_obligations_retrieved,
            "stage2_obligations_analyzed":  gap_report.stage2_obligations_analyzed,
            "hallucination_rejections":     gap_report.hallucination_rejections,
            "avg_confidence":               gap_report.avg_confidence,
            "latency_seconds":              gap_report.latency_seconds,
        },
        "risk_breakdown": {
            "critical": len(critical_gaps),
            "moderate": len(moderate_gaps),
            "info":     len(info_gaps),
        },
        "critical_gaps": [_gap_to_dict(g) for g in critical_gaps],
        "moderate_gaps": [_gap_to_dict(g) for g in moderate_gaps],
        "partial_gaps":  [_gap_to_dict(g) for g in gap_report.partial],
        "missing":       [_gap_to_dict(g) for g in gap_report.missing],
        "covered":       [_gap_to_dict(g) for g in gap_report.covered],
    }
    return report


def render_markdown(gap_report: "GapReport") -> str:
    """
    Render a full Markdown narrative report from a GapReport.

    Returns:
        Markdown string suitable for display, PDF export,
        or inclusion as a paper appendix.
    """
    frameworks = _detect_frameworks(gap_report)
    score = gap_report.overall_coverage_score
    summary = gap_report.summary

    # Determine risk level from score
    if score >= 80:
        risk_banner = "🟢 **LOW RISK** — Policy substantially covers regulatory obligations."
    elif score >= 60:
        risk_banner = "🟡 **MODERATE RISK** — Significant gaps exist. Immediate remediation recommended."
    else:
        risk_banner = "🔴 **HIGH RISK** — Critical compliance gaps detected. Urgent regulatory exposure."

    lines: List[str] = []

    # ── Header ────────────────────────────────────────────────────────────────
    lines += [
        "# AML Compliance Gap Analysis Report",
        "",
        f"**Report ID:** `{gap_report.report_id}`",
        f"**Assessment Date:** {gap_report.assessment_date[:10]}",
        f"**Regulation Snapshot (As-of Date):** {gap_report.as_of_date or 'Current'}",
        f"**Regulatory Frameworks Analyzed:** {', '.join(frameworks) if frameworks else 'All indexed'}",
        "",
        "---",
        "",
    ]

    # ── Executive Summary ─────────────────────────────────────────────────────
    lines += [
        "## Executive Summary",
        "",
        risk_banner,
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| **Overall Coverage Score** | **{score:.1f}%** |",
        f"| Obligations Analyzed | {gap_report.total_obligations_analyzed} |",
        f"| 🟢 Covered | {summary.get('covered', 0)} |",
        f"| 🟡 Partially Covered | {summary.get('partial', 0)} |",
        f"| 🔴 Missing | {summary.get('missing', 0)} |",
        f"| Avg LLM Confidence | {gap_report.avg_confidence:.1%} |",
        f"| Hallucination Rejections | {gap_report.hallucination_rejections} |",
        f"| Analysis Latency | {gap_report.latency_seconds}s |",
        "",
        "---",
        "",
    ]

    # ── Coverage Score Formula ─────────────────────────────────────────────────
    lines += [
        "## Methodology",
        "",
        "Coverage scores are computed using the weighted formula:",
        "",
        "```",
        "CoverageScore_i = (0.7 × S_sim + 0.3 × S_cite) × W_reg",
        "",
        "  S_sim  = cosine_similarity(obligation_embedding, best_policy_chunk_embedding)",
        "  S_cite = 1.0 if evidence quote verified in policy text, else 0.0",
        "  W_reg  = 1.5 (Mandatory) | 1.0 (Recommended) | 0.5 (Optional)",
        "",
        "OverallCoverage = Σ(CoverageScore_i) / Σ(W_reg_i) × 100",
        "```",
        "",
        "Evidence verification uses fuzzy substring matching (threshold ≥ 75%) to guard",
        "against hallucinated citations. Unverified evidence quotes are excluded from scoring.",
        "",
        "---",
        "",
    ]

    # ── Critical Gaps ─────────────────────────────────────────────────────────
    critical = [g for g in gap_report.missing if g.severity == "critical"]
    if critical:
        lines += [
            "## 🚨 Critical Gaps (Mandatory Obligations — Missing)",
            "",
            "> These represent the highest regulatory exposure. Mandatory obligations with no",
            "> corresponding policy clause constitute a direct breach risk.",
            "",
        ]
        for i, gap in enumerate(critical, 1):
            lines += _render_gap_section(i, gap)
            lines.append("")

    # ── Moderate Gaps ─────────────────────────────────────────────────────────
    moderate_missing = [g for g in gap_report.missing if g.severity == "moderate"]
    moderate_partial = [g for g in gap_report.partial if g.severity == "moderate"]
    moderate = moderate_missing + moderate_partial
    if moderate:
        lines += [
            "## ⚠️ Moderate Gaps",
            "",
        ]
        for i, gap in enumerate(moderate, 1):
            lines += _render_gap_section(i, gap)
            lines.append("")

    # ── Partial Coverage ──────────────────────────────────────────────────────
    info_partial = [g for g in gap_report.partial if g.severity == "info"]
    if info_partial:
        lines += [
            "## 🟡 Partial Coverage (Lower-Risk)",
            "",
        ]
        for i, gap in enumerate(info_partial, 1):
            lines.append(
                f"**{i}.** `{gap.regulation_type}` — {gap.regulation_source} "
                f"(Page {gap.regulation_page}) | Score: {gap.coverage_score:.2f}"
            )
            if gap.gap_reason:
                lines.append(f"   - _{gap.gap_reason}_")
            lines.append("")

    # ── Covered ───────────────────────────────────────────────────────────────
    if gap_report.covered:
        lines += [
            "## 🟢 Covered Obligations",
            "",
            "| Regulation | Jurisdiction | Level | Source | Score |",
            "|------------|-------------|-------|--------|-------|",
        ]
        for gap in gap_report.covered:
            lines.append(
                f"| {gap.regulation_type or '—'} | {gap.jurisdiction or '—'} "
                f"| {gap.obligation_level or '—'} | {gap.regulation_source or '—'} "
                f"| {gap.coverage_score:.2f} |"
            )
        lines.append("")

    # ── Obligation Traceability ────────────────────────────────────────────────
    all_with_path = [
        g for g in (gap_report.missing + gap_report.partial + gap_report.covered)
        if g.graph_path
    ]
    if all_with_path:
        lines += [
            "---",
            "",
            "## Regulatory Traceability Paths",
            "",
            "Each path traces the chain: **FATF Recommendation → National Law "
            "→ Regulatory Direction → Internal Policy Clause**.",
            "",
        ]
        for gap in all_with_path[:20]:  # cap at 20 for readability
            icon = _STATUS_ICON.get(gap.status, "❓")
            lines.append(f"- {icon} `{gap.graph_path}`")
        if len(all_with_path) > 20:
            lines.append(f"- _(+{len(all_with_path) - 20} more paths — see JSON report)_")
        lines.append("")

    # ── Statistical Appendix ──────────────────────────────────────────────────
    lines += [
        "---",
        "",
        "## Statistical Appendix",
        "",
        f"| Parameter | Value |",
        f"|-----------|-------|",
        f"| Stage 1 obligations retrieved (hybrid search) | {gap_report.stage1_obligations_retrieved} |",
        f"| Stage 2 obligations LLM-judged | {gap_report.stage2_obligations_analyzed} |",
        f"| LLM call reduction vs naive approach | "
        f"{_calc_llm_reduction(gap_report.stage1_obligations_retrieved, gap_report.stage2_obligations_analyzed)} |",
        f"| Hallucination guard rejections | {gap_report.hallucination_rejections} |",
        f"| Average judgment confidence | {gap_report.avg_confidence:.1%} |",
        f"| Total analysis latency | {gap_report.latency_seconds}s |",
        "",
        "> **Two-Stage Architecture**: Stage 1 uses cost-free hybrid retrieval to reduce ~300 regulatory",
        "> obligations to the top-N most relevant. Only those reach the LLM judge in Stage 2.",
        "",
        "---",
        "",
        f"*Generated by SIA-RAG AML Compliance Engine · Report ID: `{gap_report.report_id}`*",
    ]

    return "\n".join(lines)


def _render_gap_section(idx: int, gap: "GapResult") -> List[str]:
    """Render a detailed section for a single gap (missing or partial)."""
    lines = []
    icon = _STATUS_ICON.get(gap.status, "❓")
    severity_badge = f"[{gap.severity.upper()}]" if gap.severity else ""

    lines.append(
        f"### {idx}. {icon} {gap.regulation_type or 'General'} | "
        f"{gap.jurisdiction} | {severity_badge}"
    )
    lines.append("")
    lines.append(f"**Source:** {gap.regulation_source}, Page {gap.regulation_page}"
                 + (f", §{gap.regulation_section}" if gap.regulation_section else ""))
    if gap.effective_date:
        lines.append(f"**Effective:** {gap.effective_date}")
    lines.append(f"**Obligation Level:** {gap.obligation_level or 'Mandatory'}")
    lines.append(f"**Coverage Score:** {gap.coverage_score:.3f} "
                 f"(S_sim={gap.s_sim:.3f}, S_cite={gap.s_cite:.1f}, W_reg={gap.w_reg:.1f})")
    lines.append("")
    lines.append("**Regulatory Obligation:**")
    lines.append(f"> {gap.obligation_text[:500]}")
    if len(gap.obligation_text) > 500:
        lines.append("> ...")
    lines.append("")

    if gap.evidence:
        lines.append("**Closest Policy Match:**")
        lines.append(f"> _{gap.evidence[:300]}_")
        lines.append("")

    if gap.gap_reason:
        lines.append(f"**Gap Reason:** {gap.gap_reason}")
        lines.append("")

    if gap.remediation:
        lines.append("**Suggested Remediation:**")
        lines.append("")
        lines.append(f"> {gap.remediation}")
        lines.append("")

    if gap.graph_path:
        lines.append(f"**Traceability:** `{gap.graph_path}`")
        lines.append("")

    lines.append("---")
    return lines


def _calc_llm_reduction(stage1: int, stage2: int) -> str:
    """Calculate and format the LLM call reduction percentage."""
    if stage1 <= 0:
        return "N/A"
    reduction = (1 - stage2 / max(stage1, 1)) * 100
    # Assuming a naive baseline of 300 obligations
    naive = 300
    actual_reduction = (1 - stage2 / naive) * 100
    return f"~{actual_reduction:.0f}% vs 300-obligation naive baseline"
