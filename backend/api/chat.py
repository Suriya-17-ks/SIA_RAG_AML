from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Literal, List
import logging
import traceback
import json
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter()

# ── History storage directory ──────────────────────────────────────────────────
HISTORY_DIR = Path("./data/chat_history")
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

# Lazy singleton — avoids stale graph if modules reload
_graph = None

def _get_graph():
    global _graph
    if _graph is None:
        from backend.agents.graph.graph import build_graph
        logger.info("[chat] Building LangGraph pipeline...")
        _graph = build_graph()
        logger.info("[chat] Graph ready.")
    return _graph


# ── Request / Response models ──────────────────────────────────────────────────

class HistoryMessage(BaseModel):
    role: str       # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    query: str
    search_mode: Optional[Literal["auto", "pdf", "web", "both"]] = "auto"
    conversation_id: Optional[str] = None
    history: Optional[List[HistoryMessage]] = None   # last N messages for memory

class SourceRef(BaseModel):
    page: int
    source: str                     # Filename
    section: Optional[str] = None
    jurisdiction: Optional[str] = None
    regulation_type: Optional[str] = None
    score: Optional[float] = None

class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceRef] = []
    conversation_id: Optional[str] = None


# ── Main chat endpoint ─────────────────────────────────────────────────────────

@router.post("/", response_model=ChatResponse)
def chat(request: ChatRequest):
    # Map search_mode to sources
    sources = None
    if request.search_mode == "pdf":
        sources = ["pdf"]
    elif request.search_mode == "web":
        sources = ["web"]
    elif request.search_mode == "both":
        sources = ["pdf", "web"]

    # Build conversation history for memory (last 5 exchanges max)
    conversation_history = None
    if request.history:
        conversation_history = [
            {"role": m.role, "content": m.content}
            for m in request.history[-10:]  # keep last 10 messages (5 exchanges)
        ]

    initial_state = {
        "query":                request.query,
        "intent":               None,
        "retrieval":            None,
        "granularity":          None,
        "sources":              sources,
        "pdf_chunks":           [],
        "web_chunks":           [],
        "final_answer":         None,
        "conversation_history": conversation_history,
    }

    try:
        result = _get_graph().invoke(initial_state)

        # ── Extract structured sources from retrieved chunks ──────────────
        source_refs: List[SourceRef] = []
        seen = set()
        for chunk in result.get("pdf_chunks", []):
            key = (getattr(chunk, "source", ""), getattr(chunk, "page", 0))
            if key in seen:
                continue
            seen.add(key)
            source_refs.append(SourceRef(
                page=getattr(chunk, "page", 0),
                source=getattr(chunk, "source", "") or getattr(chunk, "doc_id", ""),
                section=getattr(chunk, "section_title", None),
                jurisdiction=getattr(chunk, "jurisdiction", None),
                regulation_type=getattr(chunk, "regulation_type", None),
                score=round(getattr(chunk, "score", 0) or 0, 4),
            ))

        # Sort by score descending
        source_refs.sort(key=lambda s: s.score or 0, reverse=True)

        return ChatResponse(
            answer=result["final_answer"],
            sources=source_refs[:8],  # top 8 unique sources
            conversation_id=request.conversation_id,
        )

    except Exception as exc:
        logger.error(f"[chat] Error during graph invoke: {exc}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "answer": f"❌ Server error: {exc}"},
        )


# ── Chat History Endpoints ─────────────────────────────────────────────────────

class SaveHistoryRequest(BaseModel):
    conversation_id: str
    title: str
    messages: List[HistoryMessage]

class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    message_count: int
    updated_at: float

@router.post("/history/save")
def save_history(req: SaveHistoryRequest):
    """Save or update a conversation."""
    filepath = HISTORY_DIR / f"{req.conversation_id}.json"
    data = {
        "conversation_id": req.conversation_id,
        "title": req.title,
        "messages": [m.model_dump() for m in req.messages],
        "updated_at": time.time(),
    }
    filepath.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"status": "ok", "conversation_id": req.conversation_id}


@router.get("/history/list")
def list_history():
    """List all saved conversations, newest first."""
    conversations: List[dict] = []
    for f in HISTORY_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            conversations.append(ConversationSummary(
                conversation_id=data["conversation_id"],
                title=data.get("title", "Untitled"),
                message_count=len(data.get("messages", [])),
                updated_at=data.get("updated_at", 0),
            ).model_dump())
        except Exception:
            continue

    conversations.sort(key=lambda c: c["updated_at"], reverse=True)
    return {"conversations": conversations}


@router.get("/history/{conversation_id}")
def load_history(conversation_id: str):
    """Load a specific conversation."""
    filepath = HISTORY_DIR / f"{conversation_id}.json"
    if not filepath.exists():
        return JSONResponse(status_code=404, content={"detail": "Conversation not found"})
    data = json.loads(filepath.read_text(encoding="utf-8"))
    return data


@router.delete("/history/{conversation_id}")
def delete_history(conversation_id: str):
    """Delete a conversation."""
    filepath = HISTORY_DIR / f"{conversation_id}.json"
    if filepath.exists():
        filepath.unlink()
    return {"status": "ok"}
