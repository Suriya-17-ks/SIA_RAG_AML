from backend.config.settings import settings, get_llm_client, get_model_name
from .schemas import RouterDecision
from .prompt import ROUTER_PROMPT
from .preprocessor import preprocess_query
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

# Lazy singleton — avoids stale client when LLM_PROVIDER changes between restarts
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = get_llm_client()
        logger.info(f"[router] LLM client initialised: {type(_client).__name__} | model={get_model_name('router')}")
    return _client


@lru_cache(maxsize=256)
def _cached_llm_route(query: str) -> RouterDecision:
    """
    LLM-based routing — cached by exact (normalised) query string.
    Same query asked twice → second call returns instantly (no LLM cost).
    """
    response = _get_client().chat_completion(
        model=get_model_name("router"),
        messages=[
            {"role": "system", "content": ROUTER_PROMPT},
            {"role": "user",   "content": query},
        ],
        response_format={"type": "json_object"},
        temperature=settings.temperature,
    )
    return RouterDecision.model_validate_json(response.choices[0].message.content)


def router_node(state):
    """Route queries based on intent, sources needed, and retrieval strategy."""

    query = state["query"]

    # Step 1: Preprocess query for pattern-based hints
    hints = preprocess_query(query)

    # Step 2: Check if we have high-confidence override (skip LLM entirely)
    if hints.confidence >= 0.85:
        decision = RouterDecision(
            intent=hints.suggested_intent or "summary",
            sources=["pdf"],
            retrieval=hints.suggested_retrieval or "hybrid",
            granularity=hints.suggested_granularity or "section"
        )
        logger.info(f"[router] high-confidence preprocessor ({hints.confidence:.2f}): {hints.reasoning}")
    else:
        # Step 3: LLM classification (with cache — repeated queries are free)
        normalised = query.strip().lower()
        # Copy the cached result before mutating — lru_cache returns the same
        # object on every hit, so mutating without copying corrupts the cache.
        cached    = _cached_llm_route(normalised)
        decision  = RouterDecision(
            intent=cached.intent,
            sources=list(cached.sources),
            retrieval=cached.retrieval,
            granularity=cached.granularity,
            detected_jurisdiction=cached.detected_jurisdiction,
        )
        logger.info(
            f"[router] LLM decision — intent={decision.intent} "
            f"retrieval={decision.retrieval} jurisdiction={decision.detected_jurisdiction}"
        )


        # Step 4: Apply preprocessor soft overrides where confident
        if hints.confidence >= 0.7:
            if hints.is_definitional and decision.granularity == "sentence":
                logger.info("[router] override: sentence → section (definitional query)")
                decision.granularity = "section"
                decision.intent      = "summary"
            if hints.is_technical_detail and decision.granularity == "section":
                logger.info("[router] override: section → sentence (technical detail)")
                decision.granularity = "sentence"

    state["intent"]      = decision.intent
    state["retrieval"]   = decision.retrieval
    state["granularity"] = decision.granularity
    state["detected_jurisdiction"] = decision.detected_jurisdiction  # for reranker

    if not state.get("sources"):
        state["sources"] = decision.sources

    return state

