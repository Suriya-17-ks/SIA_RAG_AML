from typing import List, Dict
from docling.document_converter import DocumentConverter
import logging

logger = logging.getLogger(__name__)

# ── Singleton converter ────────────────────────────────────────────
# DocumentConverter loads heavy ML models (layout detector, table recogniser).
# Creating it once and reusing it saves 10–30 seconds on every subsequent upload.
_converter: DocumentConverter | None = None


def get_converter() -> DocumentConverter:
    """Return the cached DocumentConverter, initialising it on first call."""
    global _converter
    if _converter is None:
        logger.info("Initialising Docling DocumentConverter (one-time cost)…")
        _converter = DocumentConverter()
        logger.info("DocumentConverter ready.")
    return _converter


def parse_pdf(file_path: str) -> List[Dict]:
    """
    Parse PDF using Docling with layout and structure preservation.
    Output format is ingestion-engine agnostic.
    """
    converter = get_converter()   # reuse cached instance
    result = converter.convert(file_path)
    doc = result.document  # Get the DoclingDocument

    parsed_blocks: List[Dict] = []

    # Iterate through all text items (paragraphs, headings, etc.)
    for item in doc.texts:
        if not item.text or not item.text.strip():
            continue

        # Get page number from provenance if available
        page_num = item.prov[0].page_no if item.prov else 1

        parsed_blocks.append({
            "text":        item.text.strip(),
            "page_number": page_num,
            "category":    item.label if hasattr(item, 'label') else "paragraph",
        })

    return parsed_blocks
