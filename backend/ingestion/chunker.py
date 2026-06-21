# Enhanced Chunker with Table Structure Preservation
from typing import List
from .schemas import StructuredChunk, ContentType
import uuid
import re

# ── Tiny-chunk constants ───────────────────────────────────────────────────
MIN_TOKENS = 10          # chunks shorter than this are skipped

# ── Heuristic header detection (for narrative PDFs docling misclassifies) ──
_NO_PUNCT_RE = re.compile(r'[.!?,;:]')

def _is_heuristic_header(text: str) -> bool:
    """
    Treat a block as a section header if it looks like one but was not
    classified as ContentType.HEADER by Docling.  Criteria:
      - Short (< 10 words)
      - Mostly upper-case (> 70 % alpha chars are uppercase)
      - No sentence-ending punctuation
      - Not purely numeric
    """
    words = text.split()
    if not (1 <= len(words) < 10):
        return False
    if _NO_PUNCT_RE.search(text):
        return False
    if text.strip().replace(' ', '').isdigit():
        return False
    alpha_chars = [c for c in text if c.isalpha()]
    if not alpha_chars:
        return False
    upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
    return upper_ratio > 0.70


def infer_content_type(category: str) -> ContentType:
    """Infer content type from Docling's category labels."""
    category_lower = category.lower()
    
    if "table" in category_lower:
        return ContentType.TABLE
    if "title" in category_lower or "heading" in category_lower:
        return ContentType.HEADER
    if "list" in category_lower:
        return ContentType.LIST
    if "figure" in category_lower or "image" in category_lower:
        return ContentType.FIGURE
    if "caption" in category_lower:
        return ContentType.CAPTION
    if "code" in category_lower:
        return ContentType.CODE
    if "warning" in category_lower or "caution" in category_lower:
        return ContentType.WARNING
    
    return ContentType.PARAGRAPH


def build_chunks(
    parsed_blocks: List[dict],
    doc_id: str,
    source: str = "",
) -> List[StructuredChunk]:
    """
    Build structured chunks with hierarchical metadata.
    Preserves section hierarchy and generates unique chunk IDs.

    Quality gates applied before a block becomes a chunk:
      1. Heuristic header promotion  — catches headers Docling missed
      2. Tiny-chunk filter           — skips blocks < MIN_TOKENS tokens
      3. Pure-digit filter           — skips page numbers / TOC entries
    """
    chunks: List[StructuredChunk] = []
    current_section = None
    current_section_id = None
    hierarchy_level = 0

    for idx, block in enumerate(parsed_blocks):
        text = block["text"].strip()
        if not text:
            continue

        content_type = infer_content_type(block["category"])

        # ── Fix 3: heuristic header detection for narrative PDFs ───────────
        if content_type != ContentType.HEADER and _is_heuristic_header(text):
            content_type = ContentType.HEADER

        # Track section hierarchy (headers update state but don't become chunks)
        if content_type == ContentType.HEADER:
            current_section = text
            current_section_id = f"{doc_id}_section_{idx}"
            hierarchy_level = 1
            continue

        # ── Fix 1: tiny-chunk filter ───────────────────────────────────────
        token_count = len(text.split())
        if token_count < MIN_TOKENS:
            continue  # skip page numbers, TOC digits, bullet fragments

        # ── Fix 1b: pure-digit filter ──────────────────────────────────────
        if text.replace(' ', '').isdigit():
            continue

        # Generate unique chunk ID
        chunk_id = f"{doc_id}_chunk_{idx}_{uuid.uuid4().hex[:8]}"

        chunk = StructuredChunk(
            doc_id=doc_id,
            content=text,
            page_number=block["page_number"],
            section_title=current_section,
            content_type=content_type,
            chunk_id=chunk_id,
            parent_section_id=current_section_id,
            hierarchy_level=hierarchy_level,
            source=source,
        )

        chunks.append(chunk)

    return chunks
