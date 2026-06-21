from backend.config.settings import settings, get_llm_client, get_model_name
from backend.config.prompts import VERIFIER_PROMPT
import logging

logger = logging.getLogger(__name__)

# Lazy singleton — avoids stale client when LLM_PROVIDER changes between restarts
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = get_llm_client()
        logger.info(f"[verifier] LLM client initialised: {type(_client).__name__} | model={get_model_name('verifier')}")
    return _client


def verifier_node(state):
    """
    Synthesize final answer from PDF and Web chunks with mandatory citation enforcement.
    Caps context to max_context_chunks best chunks → shorter prompt, faster response.
    """
    pdf_chunks = state.get("pdf_chunks", [])
    web_chunks = state.get("web_chunks", [])

    # Handle empty results
    if not pdf_chunks and not web_chunks:
        state["final_answer"] = (
            "❌ No traceable information was found in the available sources. "
            "Please try rephrasing your question or check if relevant documents have been uploaded."
        )
        return state

    # ── Cap context size ──────────────────────────────────────────────
    max_chunks = settings.max_context_chunks

    # Sort PDF chunks by score (highest first) and keep top N
    pdf_chunks_sorted = sorted(pdf_chunks, key=lambda c: getattr(c, "score", 0), reverse=True)
    pdf_chunks_used   = pdf_chunks_sorted[:max_chunks]
    pdf_dropped       = len(pdf_chunks) - len(pdf_chunks_used)

    # Web chunks fill remaining slots
    remaining = max(0, max_chunks - len(pdf_chunks_used))
    web_chunks_used = web_chunks[:remaining]

    if pdf_dropped:
        logger.debug(f"[verifier] dropped {pdf_dropped} low-score PDF chunks (limit={max_chunks})")

    # ── Build context with citations ───────────────────────────────────
    # Truncation constants — keep total prompt well under HF's 32k token limit
    MAX_CHARS_PER_CHUNK = 1200   # ~300 tokens per chunk
    MAX_TOTAL_CHARS    = 12000   # ~3000 tokens total context

    context_blocks = []
    total_chars = 0

    for c in pdf_chunks_used:
        label = c.source or c.doc_id  # show filename, fall back to UUID
        citation = f"[Source: {label}, Page {c.page}]"
        if c.section_title:
            citation += f" §{c.section_title}"
        # ── AML metadata in citation ──────────────────────────────────────────
        aml_parts = []
        if getattr(c, "jurisdiction", None):
            aml_parts.append(f"Jurisdiction: {c.jurisdiction}")
        if getattr(c, "regulation_type", None):
            aml_parts.append(f"Type: {c.regulation_type}")
        if getattr(c, "obligation_level", None):
            aml_parts.append(f"Level: {c.obligation_level}")
        if getattr(c, "effective_date", None):
            aml_parts.append(f"Effective: {c.effective_date}")
        if aml_parts:
            citation += f" [{', '.join(aml_parts)}]"
        # ────────────────────────────────────────────────────────────────────
        content_trimmed = c.content[:MAX_CHARS_PER_CHUNK]
        if len(c.content) > MAX_CHARS_PER_CHUNK:
            content_trimmed += "…"
        block = f"{citation}\n{content_trimmed}"
        if total_chars + len(block) > MAX_TOTAL_CHARS:
            break
        context_blocks.append(block)
        total_chars += len(block)

    for w in web_chunks_used:
        reliability_indicator = "⭐" * int(w.reliability * 5)
        citation = f"[WEB | {w.url} | Trust: {w.reliability:.2f} {reliability_indicator} | Type: {w.source_type}]"
        if w.title:
            citation += f"\nTitle: {w.title}"
        content_trimmed = w.content[:MAX_CHARS_PER_CHUNK]
        if len(w.content) > MAX_CHARS_PER_CHUNK:
            content_trimmed += "…"
        block = f"{citation}\n{content_trimmed}"
        if total_chars + len(block) > MAX_TOTAL_CHARS:
            break
        context_blocks.append(block)
        total_chars += len(block)

    context = "\n\n---\n\n".join(context_blocks)

    # ── Intent-specific guidance ──────────────────────────────────────
    intent = state.get("intent", "summary")
    intent_guidance = ""
    if intent == "summary":
        intent_guidance = """
QUERY TYPE: DEFINITIONAL/SUMMARY
- This is a 'what is', 'define', or 'explain' type question
- START with high-level definitions from Introduction/Abstract sections
- AVOID starting with technical formulas or implementation details
- Provide conceptual understanding first, technical details only if relevant
"""
    elif intent == "fact":
        intent_guidance = """
QUERY TYPE: SPECIFIC FACT
- Extract the precise fact, value, or specification requested
- Use technical details and specifics if available
"""
    elif intent == "comparison":
        intent_guidance = """
QUERY TYPE: COMPARISON
- Structure answer to compare both items clearly
- Highlight similarities and differences
"""
    # ── AML-specific intent guidance ──────────────────────────────────
    elif intent == "regulatory_lookup":
        intent_guidance = """
QUERY TYPE: REGULATORY LOOKUP
- This question asks what a specific regulation requires
- CITE the exact regulatory source, jurisdiction, and effective date
- Include specific thresholds, deadlines, or procedural requirements if present
- Format: "According to [Source] (Jurisdiction, effective [date]), [requirement]..."
- Do NOT speculate beyond what the regulatory text says
"""
    elif intent == "gap_analysis":
        intent_guidance = """
QUERY TYPE: COMPLIANCE GAP ANALYSIS
- Determine whether the internal policy satisfies the regulatory requirement
- CLEARLY state: COVERED / PARTIALLY COVERED / MISSING
- For COVERED: quote the specific policy clause that satisfies the requirement
- For PARTIAL: explain what is present and what is missing
- For MISSING: state that no corresponding policy clause was found
- ALWAYS cite both the regulatory source AND the policy source
"""
    elif intent == "cross_jurisdiction":
        intent_guidance = """
QUERY TYPE: CROSS-JURISDICTION COMPARISON
- Compare regulatory requirements across two or more jurisdictions
- Use a structured format: highlight key similarities and differences
- Note which jurisdiction has stricter requirements and why
- Cite specific sources from each jurisdiction with jurisdiction labels
"""
    elif intent == "remediation":
        intent_guidance = """
QUERY TYPE: REMEDIATION SUGGESTION
- Suggest specific policy language or clauses to address the compliance gap
- Base all suggestions STRICTLY on retrieved regulatory text — do not invent rules
- Format suggested policy language as a blockquote or clearly labelled section
- Indicate which regulatory obligation each suggestion addresses
"""

    # ── LLM synthesis ─────────────────────────────────────────────────
    user_prompt = f"""QUESTION TO ANSWER:
{state['query']}
{intent_guidance}
IMPORTANT: Answer ONLY this specific question. Do not provide a general summary of the documents.

AVAILABLE CONTEXT (use ONLY this information):
{context}

Now answer the question above using only the provided context."""

    # ── Build LLM messages with optional conversation history ────────
    llm_messages = [{"role": "system", "content": VERIFIER_PROMPT}]

    # Inject conversation history for memory/context awareness
    conv_history = state.get("conversation_history") or []
    if conv_history:
        for msg in conv_history:
            llm_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })
        logger.debug(f"[verifier] Injected {len(conv_history)} history messages for context")

    llm_messages.append({"role": "user", "content": user_prompt})

    response = _get_client().chat_completion(
        model=get_model_name("verifier"),
        messages=llm_messages,
        temperature=settings.temperature,
    )

    final_answer = response.choices[0].message.content

    # ── Footer ─────────────────────────────────────────────────────────
    footer = (
        f"\n\n---\n📊 Sources: {len(pdf_chunks_used)} PDF chunks"
        f"{f' (+{pdf_dropped} dropped)' if pdf_dropped else ''}"
        f", {len(web_chunks_used)} Web sources"
    )
    if state.get("zoomed_out"):
        footer += "\n🔍 Note: Zoomed out to section-level retrieval for broader context"

    state["final_answer"] = final_answer + footer
    return state

