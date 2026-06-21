from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from backend.agents.schemas.gap_schemas import GapAnalysisRequest, GapAnalysisResponse
from backend.agents.gap_detector import GapDetector
from backend.agents.report_generator import generate_report, render_markdown
from backend.graph.obligation_graph import ObligationGraph
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory cache: report_id → (GapReport, markdown_text)
_report_cache: dict = {}


@router.post("/", response_model=GapAnalysisResponse)
async def run_gap_analysis(request: GapAnalysisRequest):
    """
    Run the two-stage compliance gap analysis on an ingested internal policy document.

    Returns a GapAnalysisResponse that includes the full GapReport plus
    a generated structured JSON dict and Markdown narrative summary.
    """
    if not request.policy_doc_id:
        raise HTTPException(status_code=400, detail="policy_doc_id is required")

    logger.info(f"Starting gap analysis for policy {request.policy_doc_id}")

    detector = GapDetector()
    try:
        report = detector.analyze(
            policy_doc_id          = request.policy_doc_id,
            as_of_date             = request.as_of_date,
            jurisdiction_filter    = request.jurisdiction_filter,
            regulation_type_filter = request.regulation_type_filter,
            max_obligations        = request.max_obligations,
        )

        # ── Obligation graph ──────────────────────────────────────────────────
        try:
            graph = ObligationGraph()
            graph.populate_from_gap_report(report)  # also sets gap.graph_path on each result
            os.makedirs("./data", exist_ok=True)
            graph.save("./data/aml_obligation_graph")
            logger.info("Obligation graph saved to ./data/")
        except Exception as ge:
            logger.warning(f"Graph build failed (non-fatal): {ge}")

        # ── Report generation ─────────────────────────────────────────────────
        report_dict = generate_report(report)
        md_text     = render_markdown(report)

        # Populate regulatory_frameworks from generated report
        report.regulatory_frameworks = report_dict.get("regulatory_frameworks", [])

        # Cache for markdown download endpoint
        _report_cache[report.report_id] = md_text

        return GapAnalysisResponse(
            report   = report,
            message  = "Gap analysis completed successfully",
            markdown = md_text,
        )

    except Exception as e:
        logger.error(f"Gap analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{report_id}/markdown", response_class=PlainTextResponse)
async def get_report_markdown(report_id: str):
    """
    Return the Markdown narrative for a previously generated gap analysis report.
    Useful for downloading / exporting the report.
    """
    md = _report_cache.get(report_id)
    if md is None:
        raise HTTPException(
            status_code=404,
            detail=f"Report '{report_id}' not found in cache. Re-run the analysis to regenerate."
        )
    return PlainTextResponse(content=md, media_type="text/markdown")
