from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from backend.api.upload import router as upload_router
from backend.api.chat import router as chat_router
from backend.api.visualization import router as visualization_router
from backend.api.documents import router as documents_router
from backend.api.gap_analysis import router as gap_analysis_router
from backend.api.transcribe import router as transcribe_router
from backend.monitoring.metrics import MetricsMiddleware
import logging
import os

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SIA-RAG Backend",
    description="Structurally Intelligent Adaptive RAG",
    version="0.1.0",
)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom metrics tracking middleware
app.add_middleware(MetricsMiddleware)

# ── Global exception handler ──────────────────────────────────────────────────
# FastAPI's default 500 response bypasses CORS middleware, so the browser sees
# no Access-Control-Allow-Origin header and reports a CORS error instead of the
# real error. This handler ensures every error response includes CORS headers.
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"},
    )

@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to the chat UI."""
    return RedirectResponse(url="/ui/index.html")

app.include_router(upload_router, prefix="/upload", tags=["Upload"])
app.include_router(chat_router,   prefix="/chat",   tags=["Chat"])
app.include_router(visualization_router, prefix="/visualize", tags=["Visualization"])
app.include_router(documents_router,     prefix="/documents", tags=["Documents"])
app.include_router(gap_analysis_router,  prefix="/gap-analysis", tags=["Gap Analysis"])
app.include_router(transcribe_router,    prefix="/transcribe", tags=["Transcribe"])

# ── Serve frontend static files ───────────────────────────────────────────────
# Mount AFTER API routes so /api/* routes take priority.
# Access the UI at http://localhost:8000  (auto-redirects to /ui/index.html)
_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
_frontend_dir = os.path.normpath(_frontend_dir)
if os.path.isdir(_frontend_dir):
    app.mount("/ui", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
    logger.info(f"[app] Frontend served from {_frontend_dir} at /ui")
else:
    logger.warning(f"[app] Frontend directory not found at {_frontend_dir}")
