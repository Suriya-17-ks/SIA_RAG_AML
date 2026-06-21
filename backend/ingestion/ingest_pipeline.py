from .pdf_parser import parse_pdf
from .chunker import build_chunks
from .aml_tagger import tag_chunks
from backend.storage.chroma_client import ChromaStore, get_aml_store
from datetime import date
import uuid
import logging
import numpy as np

logger = logging.getLogger(__name__)

# Near-duplicate threshold — chunks with cosine > this are skipped
DEDUP_THRESHOLD = 0.95


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    an, bn = np.linalg.norm(a), np.linalg.norm(b)
    if an == 0 or bn == 0:
        return 0.0
    return float(np.dot(a, b) / (an * bn))


def _dedup_chunks(chunks, embedding_fn):
    """
    Fix 2: Remove near-duplicate chunks within the same document.

    Algorithm (runs AFTER tiny-chunk filter has already eliminated garbage):
      1. Embed all chunks in one batch (fast)
      2. Greedily keep a chunk only if it has cosine < DEDUP_THRESHOLD
         to every already-accepted chunk from the same doc_id
      3. Cross-document pairs are never compared — a valid chunk that appears
         in two PDFs should be kept in both.

    Returns filtered list and a count of dropped chunks for logging.
    """
    if not chunks:
        return chunks, 0

    # Batch embed all chunk contents at once
    texts = [c.content for c in chunks]
    embeddings = embedding_fn(texts)           # returns np.ndarray (N, dim)
    embs = np.array(embeddings, dtype=float)
    norms = np.linalg.norm(embs, axis=1, keepdims=True)
    norms[norms == 0] = 1
    embs_norm = embs / norms

    kept = []
    kept_embs = {}   # doc_id -> list of normalised embeddings

    for i, chunk in enumerate(chunks):
        doc_id = chunk.doc_id
        existing = kept_embs.get(doc_id, [])

        is_dup = False
        for prev_emb in existing:
            if float(np.dot(embs_norm[i], prev_emb)) > DEDUP_THRESHOLD:
                is_dup = True
                break

        if not is_dup:
            kept.append(chunk)
            kept_embs.setdefault(doc_id, []).append(embs_norm[i])

    dropped = len(chunks) - len(kept)
    return kept, dropped


def ingest_pdf(file_path: str, doc_name: str = None) -> str:
    """
    Full ingestion pipeline with dual-granularity indexing:
    PDF -> structured chunks -> both micro and macro vector DBs

    Quality gates (in order):
      1. Tiny-chunk filter    (in chunker.py  — MIN_TOKENS < 10)
      2. Near-duplicate dedup (here           — cosine > 0.95, per-document)
      3. Insert into ChromaDB

    Args:
        file_path: Path to PDF file
        doc_name:  Human-readable document name stored in chunk metadata

    Returns:
        Document ID
    """
    doc_id = str(uuid.uuid4())
    source = doc_name or doc_id

    # Step A: Parse PDF with structural awareness
    parsed_blocks = parse_pdf(file_path)

    # Step B: Build micro chunks (tiny-chunk + heuristic-header filters applied)
    chunks = build_chunks(parsed_blocks, doc_id, source=source)
    logger.info(f"[ingest] {source}: {len(chunks)} chunks after tiny-filter")

    # Step C: Near-duplicate dedup (Fix 2)
    micro_store = ChromaStore(granularity="micro")
    embed_fn = lambda texts: micro_store.embedding_fn(texts)   # reuse existing model
    chunks, dropped = _dedup_chunks(chunks, embed_fn)
    if dropped:
        logger.info(f"[ingest] {source}: dropped {dropped} near-duplicate chunks "
                    f"(cosine > {DEDUP_THRESHOLD})")

    # Step D: Store micro chunks
    micro_store.add_chunks(chunks)
    logger.info(f"[ingest] {source}: {len(chunks)} micro chunks indexed")

    # Step E: Aggregate to section-level macro chunks and store
    macro_store = ChromaStore(granularity="macro")
    macro_chunks = _aggregate_to_sections(chunks, source=source)
    macro_store.add_chunks(macro_chunks)
    logger.info(f"[ingest] {source}: {len(macro_chunks)} macro sections indexed")

    return doc_id


def _aggregate_to_sections(chunks, source: str = ""):
    """Aggregate fine-grained chunks into section-level chunks."""
    from backend.ingestion.schemas import StructuredChunk, ContentType
    
    sections = {}
    for chunk in chunks:
        section_key = chunk.section_title or "Introduction"
        
        if section_key not in sections:
            sections[section_key] = {
                "content": [],
                "doc_id": chunk.doc_id,
                "page_number": chunk.page_number,
                "section_title": section_key
            }
        
        sections[section_key]["content"].append(chunk.content)
    
    # Convert aggregated sections to chunks
    macro_chunks = []
    for section_title, data in sections.items():
        macro_chunk = StructuredChunk(
            doc_id=data["doc_id"],
            content="\n".join(data["content"]),
            page_number=data["page_number"],
            section_title=section_title,
            content_type=ContentType.HEADER,
            chunk_id=f"{data['doc_id']}_section_{section_title}",
            hierarchy_level=1,
            source=source,
        )
        macro_chunks.append(macro_chunk)
    
    return macro_chunks


# ── AML-Specific Ingestion Functions ──────────────────────────────────────────

def ingest_regulatory_pdf(
    file_path: str,
    doc_name: str = None,
    effective_date: date = None,
    regulation_version: str = None,
    jurisdiction: str = None,
    tag_mode: str = "hybrid",
) -> str:
    """
    Ingest a regulatory PDF (FATF, RBI, PMLA, FIU-IND, etc.) into the
    dedicated `aml_regulatory` ChromaDB collection.

    Tags each chunk with AML metadata and versioning fields so that
    temporal queries ("compliant as of date X") work correctly.

    Args:
        file_path:          Path to the regulatory PDF
        doc_name:           Human-readable name (e.g. "RBI-KYC-Master-Direction-2023")
        effective_date:     Date from which this regulation applies
        regulation_version: Version string (e.g. "2023-Q4", "Amendment-7")
        jurisdiction:       Pre-assigned jurisdiction (e.g. "RBI") — overrides tagging
        tag_mode:           AML tagging mode: "rules" | "llm" | "hybrid"

    Returns:
        Document ID (UUID)
    """
    doc_id = str(uuid.uuid4())
    source = doc_name or doc_id
    today  = date.today()

    logger.info(f"[ingest_regulatory] starting: {source}")

    # Step A: Parse PDF
    parsed_blocks = parse_pdf(file_path)

    # Step B: Build chunks
    chunks = build_chunks(parsed_blocks, doc_id, source=source)
    logger.info(f"[ingest_regulatory] {source}: {len(chunks)} raw chunks")

    # Step C: Dedup
    reg_store = get_aml_store("regulatory")
    embed_fn  = lambda texts: reg_store.embedding_fn(texts)
    chunks, dropped = _dedup_chunks(chunks, embed_fn)
    if dropped:
        logger.info(f"[ingest_regulatory] {source}: dropped {dropped} near-duplicate chunks")

    # Step D: AML tagging (sets regulation_type, obligation_level, jurisdiction, entity_type)
    tag_chunks(chunks, mode=tag_mode, document_tier="regulatory")

    # Step E: Apply versioning metadata to every chunk
    for chunk in chunks:
        chunk.ingestion_date      = today
        chunk.effective_date      = effective_date
        chunk.regulation_version  = regulation_version
        # Allow caller to override jurisdiction (e.g. force "RBI" for an entire doc)
        if jurisdiction and not chunk.jurisdiction:
            chunk.jurisdiction = jurisdiction

    # Step F: Index in regulatory collection
    reg_store.add_chunks(chunks)
    logger.info(
        f"[ingest_regulatory] {source}: {len(chunks)} chunks indexed → aml_regulatory "
        f"(effective={effective_date}, version={regulation_version})"
    )

    return doc_id


def ingest_policy_pdf(
    file_path: str,
    doc_name: str = None,
    tag_mode: str = "hybrid",
) -> str:
    """
    Ingest an internal bank/NBFC AML policy PDF into the dedicated
    `aml_internal_policy` ChromaDB collection.

    Args:
        file_path:  Path to the policy PDF
        doc_name:   Human-readable name (e.g. "HDFC-AML-Policy-2024")
        tag_mode:   AML tagging mode for the policy content

    Returns:
        Document ID (UUID)
    """
    doc_id = str(uuid.uuid4())
    source = doc_name or doc_id
    today  = date.today()

    logger.info(f"[ingest_policy] starting: {source}")

    # Step A: Parse PDF
    parsed_blocks = parse_pdf(file_path)

    # Step B: Build chunks
    chunks = build_chunks(parsed_blocks, doc_id, source=source)
    logger.info(f"[ingest_policy] {source}: {len(chunks)} raw chunks")

    # Step C: Dedup
    pol_store = get_aml_store("internal_policy")
    embed_fn  = lambda texts: pol_store.embedding_fn(texts)
    chunks, dropped = _dedup_chunks(chunks, embed_fn)
    if dropped:
        logger.info(f"[ingest_policy] {source}: dropped {dropped} near-duplicate chunks")

    # Step D: AML tagging (identifies which AML topics the policy covers)
    tag_chunks(chunks, mode=tag_mode, document_tier="internal_policy")

    # Step E: Set ingestion date
    for chunk in chunks:
        chunk.ingestion_date = today

    # Step F: Index in internal policy collection
    pol_store.add_chunks(chunks)
    logger.info(f"[ingest_policy] {source}: {len(chunks)} chunks indexed → aml_internal_policy")

    return doc_id
