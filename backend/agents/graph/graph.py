from langgraph.graph import StateGraph, END
from backend.agents.graph.state import GraphState
from backend.agents.router.router import router_node
from backend.agents.graph.nodes import retrieve_pdf_node
from backend.agents.graph.web_node import retrieve_web_node
from backend.agents.verifier.verifier import verifier_node
import logging

logger = logging.getLogger(__name__)

# ── AML Gap Analysis Node ──────────────────────────────────────────────────────

def gap_analysis_node(state: GraphState) -> GraphState:
    """
    LangGraph node for compliance gap analysis.

    Triggered when router.intent is in AML_GAP_INTENTS.
    Bypasses PDF/web retrieval and calls GapDetector directly.
    Returns a formatted markdown GapReport as the final_answer.
    """
    from backend.agents.gap_detector import GapDetector
    from backend.graph.obligation_graph import ObligationGraph

    intent              = state.get("intent", "gap_analysis")
    aml_regulation_type = state.get("aml_regulation_type")
    jurisdiction        = state.get("jurisdiction_filter")
    as_of_date          = state.get("as_of_date")
    policy_doc_id       = state.get("policy_doc_id", "")

    if not policy_doc_id:
        state["final_answer"] = (
            "⚠️ No internal policy document has been ingested yet. "
            "Please upload your AML policy PDF first using the /ingest endpoint."
        )
        return state

    logger.info(
        f"[gap_analysis_node] intent={intent} "
        f"regulation_type={aml_regulation_type} jurisdiction={jurisdiction}"
    )

    try:
        detector = GapDetector()
        report   = detector.analyze(
            policy_doc_id          = policy_doc_id,
            as_of_date             = as_of_date,
            jurisdiction_filter    = jurisdiction,
            regulation_type_filter = aml_regulation_type,
        )

        # ── Populate obligation graph with gap results ──────────────────────
        try:
            graph = ObligationGraph()
            graph.populate_from_gap_report(report)
            import os
            os.makedirs("./data", exist_ok=True)
            graph.save("./data/aml_obligation_graph")
            logger.info("[gap_analysis_node] Obligation graph saved to ./data/")
        except Exception as ge:
            logger.warning(f"[gap_analysis_node] Graph build failed (non-fatal): {ge}")

        # ── Format GapReport as readable markdown ───────────────────────────
        n_missing = len(report.missing)
        n_partial = len(report.partial)
        n_covered = len(report.covered)
        score     = report.overall_coverage_score
        score_bar = _make_score_bar(score)

        lines = [
            "# AML Compliance Gap Analysis Report",
            "",
            f"**Policy Document:** {report.policy_source}",
            f"**Assessment Date:** {report.assessment_date[:10]}",
            f"**As Of Date:** {report.as_of_date or 'Latest'}",
            "",
            f"## 📊 Overall Coverage Score: {score:.1f}%",
            score_bar,
            "",
            "| Status | Count |",
            "|--------|-------|",
            f"| 🔴 Missing | {n_missing} |",
            f"| 🟡 Partial | {n_partial} |",
            f"| 🟢 Covered | {n_covered} |",
            f"| **Total** | **{report.total_obligations_analyzed}** |",
            "",
        ]

        if report.missing:
            lines.append("## 🔴 Critical Gaps — Missing Obligations\n")
            for gap in report.missing[:10]:
                lines.append(
                    f"### {gap.regulation_type or 'Obligation'} — "
                    f"{gap.regulation_source}, p.{gap.regulation_page}"
                )
                lines.append(
                    f"**Jurisdiction:** {gap.jurisdiction or 'N/A'} | "
                    f"**Level:** {gap.obligation_level or 'Mandatory'} | "
                    f"**Severity:** {gap.severity.upper()}"
                )
                lines.append(f"> {gap.obligation_text[:300]}…")
                if gap.gap_reason:
                    lines.append(f"\n❌ **Gap:** {gap.gap_reason}")
                if gap.remediation:
                    lines.append(f"\n💡 **Suggested Remedy:** {gap.remediation}")
                if gap.graph_path:
                    lines.append(f"\n🔗 **Trace:** `{gap.graph_path}`")
                lines.append("")

        if report.partial:
            lines.append("## 🟡 Partial Coverage — Incomplete Obligations\n")
            for gap in report.partial[:5]:
                lines.append(
                    f"- **{gap.regulation_type or 'Obligation'}** "
                    f"({gap.regulation_source}, p.{gap.regulation_page}): "
                    f"{gap.gap_reason or 'Incomplete coverage'}"
                )
            lines.append("")

        lines.append(
            f"---\n"
            f"📈 Analysed: {report.total_obligations_analyzed} obligations | "
            f"⏱ {report.latency_seconds:.1f}s | "
            f"🛡 Hallucination rejections: {report.hallucination_rejections} | "
            f"🎯 Avg confidence: {report.avg_confidence:.0%}"
        )

        state["final_answer"] = "\n".join(lines)

    except Exception as exc:
        logger.error(f"[gap_analysis_node] Error: {exc}", exc_info=True)
        state["final_answer"] = (
            f"❌ Gap analysis failed: {exc}\n\n"
            "Please ensure regulatory documents and the internal policy have been ingested first."
        )

    return state


def _make_score_bar(score: float, width: int = 20) -> str:
    """Visual progress bar for coverage score."""
    filled = int(round(score / 100 * width))
    return f"`[{'█' * filled}{'░' * (width - filled)}] {score:.1f}%`"


# ── Intent routing ─────────────────────────────────────────────────────────────

# These intents skip PDF/web retrieval and go directly to gap analysis
AML_GAP_INTENTS = {"gap_analysis", "remediation"}


def route_after_router(state: GraphState):
    """Route to appropriate nodes based on intent and sources needed."""
    intent  = state.get("intent", "summary")
    sources = state.get("sources", [])

    # AML gap analysis intents bypass retrieval
    if intent in AML_GAP_INTENTS:
        return "gap_analysis"

    if not sources:
        return "verifier"

    if "pdf" in sources and "web" in sources:
        return ["retrieve_pdf", "retrieve_web"]
    elif "pdf" in sources:
        return "retrieve_pdf"
    elif "web" in sources:
        return "retrieve_web"

    return "verifier"


def merge_and_verify(state: GraphState):
    """Merge retrieval results and route to verifier."""
    return "verifier"


def build_graph():
    """Build the LangGraph workflow with parallel retrieval and AML gap analysis."""
    graph = StateGraph(GraphState)

    # ── Nodes ──────────────────────────────────────────────────────────────────
    graph.add_node("router",       router_node)
    graph.add_node("retrieve_pdf", retrieve_pdf_node)
    graph.add_node("retrieve_web", retrieve_web_node)
    graph.add_node("verifier",     verifier_node)
    graph.add_node("gap_analysis", gap_analysis_node)   # AML gap detection

    # ── Entry point ────────────────────────────────────────────────────────────
    graph.set_entry_point("router")

    # ── Conditional routing ────────────────────────────────────────────────────
    graph.add_conditional_edges(
        "router",
        route_after_router,
        {
            "retrieve_pdf": "retrieve_pdf",
            "retrieve_web": "retrieve_web",
            "verifier":     "verifier",
            "gap_analysis": "gap_analysis",
        },
    )

    # ── Convergence ────────────────────────────────────────────────────────────
    graph.add_edge("retrieve_pdf", "verifier")
    graph.add_edge("retrieve_web", "verifier")

    # ── Terminal nodes ─────────────────────────────────────────────────────────
    graph.add_edge("verifier",     END)
    graph.add_edge("gap_analysis", END)

    return graph.compile()
