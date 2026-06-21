import chromadb
from chromadb.utils import embedding_functions
from typing import List, Optional, Dict, Any
from backend.config.settings import settings
from backend.ingestion.schemas import StructuredChunk, DocumentChunk
import logging

logger = logging.getLogger(__name__)


def _resolve_device() -> str:
    """
    Resolve the embedding device at startup:
      auto  → tries cuda → mps → cpu
      cuda  → NVIDIA GPU (requires torch + CUDA)
      mps   → Apple Silicon GPU
      cpu   → always works
    """
    device = settings.embedding_device.lower()
    if device != "auto":
        return device

    try:
        import torch
        if torch.cuda.is_available():
            gpu = torch.cuda.get_device_name(0)
            logger.info(f"GPU detected: {gpu} — using cuda for embeddings")
            return "cuda"
        if torch.backends.mps.is_available():
            logger.info("Apple MPS GPU detected — using mps for embeddings")
            return "mps"
    except ImportError:
        pass

    logger.info("No GPU detected — using cpu for embeddings")
    return "cpu"


# Device resolution is now lazy to prevent PyTorch from blocking server boot
_EMBEDDING_DEVICE = None

def get_device() -> str:
    global _EMBEDDING_DEVICE
    if _EMBEDDING_DEVICE is None:
        _EMBEDDING_DEVICE = _resolve_device()
    return _EMBEDDING_DEVICE

# ── AML collection name constants ─────────────────────────────────────────────
COLLECTION_REGULATORY     = "aml_regulatory"       # FATF, RBI, PMLA, FIU-IND docs
COLLECTION_INTERNAL_POLICY = "aml_internal_policy"  # Bank/NBFC policy PDFs


class ChromaStore:
    """
    Persistent vector store with dual-granularity and dual-index support.

    Index axes:
      granularity : "micro" (sentence) | "macro" (section) — existing behaviour
      index_type  : "regulatory" | "internal_policy"       — NEW for AML domain
                    When index_type is set, a dedicated AML collection is used
                    instead of the generic micro/macro collections.
    """

    def __init__(
        self,
        collection_name: Optional[str] = None,
        granularity: str = "micro",
        index_type: Optional[str] = None,   # "regulatory" | "internal_policy"
    ):
        self.client = chromadb.PersistentClient(path=settings.chroma_persist_directory)

        if settings.embedding_provider == "local":
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=settings.embedding_model,
                device=get_device(),
            )
        else:
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY required when using OpenAI embeddings")
            self.embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
                api_key=settings.openai_api_key,
                model_name=settings.openai_embedding_model
            )

        # ── Collection selection ───────────────────────────────────────────────
        if collection_name is not None:
            # Explicit override (e.g. test code)
            resolved_name = collection_name
        elif index_type == "regulatory":
            resolved_name = COLLECTION_REGULATORY
        elif index_type == "internal_policy":
            resolved_name = COLLECTION_INTERNAL_POLICY
        else:
            # Legacy behaviour: micro/macro generic collections
            resolved_name = (
                settings.collection_micro if granularity == "micro"
                else settings.collection_macro
            )

        self.collection_name = resolved_name
        self.index_type = index_type
        self.collection = self.client.get_or_create_collection(
            name=resolved_name,
            embedding_function=self.embedding_fn,
            metadata={"granularity": granularity, "index_type": index_type or "generic"}
        )

    def add_chunks(self, chunks: List[StructuredChunk]):
        """Add structured chunks to the vector database, including all AML metadata."""
        if not chunks:
            return

        def _safe_str(val) -> str:
            """ChromaDB metadata values must be str/int/float/bool — never None."""
            if val is None:
                return ""
            return str(val)

        self.collection.add(
            documents=[c.content for c in chunks],
            metadatas=[
                {
                    # ── Core structural metadata ──────────────────────────────
                    "doc_id":            c.doc_id,
                    "source":            c.source,
                    "page_number":       c.page_number,
                    "section_title":     c.section_title or "",
                    "content_type":      c.content_type.value,
                    "chunk_id":          c.chunk_id or "",
                    "parent_section_id": c.parent_section_id or "",
                    "hierarchy_level":   c.hierarchy_level,
                    # ── AML domain metadata ───────────────────────────────────
                    "regulation_type":   _safe_str(c.regulation_type),
                    "obligation_level":  _safe_str(c.obligation_level),
                    "jurisdiction":      _safe_str(c.jurisdiction),
                    "entity_type":       _safe_str(c.entity_type),
                    "document_tier":     _safe_str(c.document_tier),
                    # ── Versioning ────────────────────────────────────────────
                    "regulation_version": _safe_str(c.regulation_version),
                    "effective_date":    _safe_str(c.effective_date),   # ISO date string
                    "ingestion_date":    _safe_str(c.ingestion_date),
                    "supersedes":        _safe_str(c.supersedes),
                }
                for c in chunks
            ],
            ids=[c.chunk_id or f"{c.doc_id}_{i}" for i, c in enumerate(chunks)]
        )

    def query(
        self,
        query_text: str,
        k: int = None,
        where: Optional[Dict[str, Any]] = None,
        as_of_date: Optional[str] = None,          # ISO date string "YYYY-MM-DD"
        regulation_type: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        document_tier: Optional[str] = None,
    ) -> List[DocumentChunk]:
        """
        Query the collection with optional metadata filtering.

        Args:
            query_text:      The search query
            k:               Number of results to return
            where:           Raw ChromaDB metadata filters (overrides individual params)
            as_of_date:      Only return chunks where effective_date <= as_of_date
                             (temporal compliance filtering — "compliant as of X")
            regulation_type: Filter by AML type (e.g. "CTR", "PEP")
            jurisdiction:    Filter by jurisdiction (e.g. "RBI", "FATF")
            document_tier:   Filter by tier ("regulatory" | "internal_policy")

        Returns:
            List of DocumentChunk objects with AML metadata populated
        """
        k = k or settings.default_k

        # ── Build metadata filter ──────────────────────────────────────────────
        if where is None and any([regulation_type, jurisdiction, document_tier]):
            conditions = []
            if regulation_type:
                conditions.append({"regulation_type": {"$eq": regulation_type}})
            if jurisdiction:
                conditions.append({"jurisdiction": {"$eq": jurisdiction}})
            if document_tier:
                conditions.append({"document_tier": {"$eq": document_tier}})

            where = {"$and": conditions} if len(conditions) > 1 else conditions[0]

        results = self.collection.query(
            query_texts=[query_text],
            n_results=k,
            where=where if where else None
        )

        # ── Parse results → DocumentChunk ──────────────────────────────────────
        chunks = []
        if results and results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i]
                chunk_id = results['ids'][0][i]
                distance = results['distances'][0][i] if 'distances' in results else None

                # ── Temporal filtering (post-query, ChromaDB can't do date range) ──
                if as_of_date:
                    eff = metadata.get("effective_date", "")
                    # Skip chunks whose regulation was NOT yet effective at as_of_date
                    if eff and eff > as_of_date:
                        continue

                chunks.append(DocumentChunk(
                    id=chunk_id,
                    content=doc,
                    doc_id=metadata.get('doc_id', ''),
                    source=metadata.get('source', ''),
                    page=metadata.get('page_number', 0),
                    section_title=metadata.get('section_title') or None,
                    content_type=metadata.get('content_type', 'paragraph'),
                    score=1 - distance if distance is not None else None,
                    # AML metadata
                    regulation_type=metadata.get('regulation_type') or None,
                    obligation_level=metadata.get('obligation_level') or None,
                    jurisdiction=metadata.get('jurisdiction') or None,
                    document_tier=metadata.get('document_tier') or None,
                    effective_date=metadata.get('effective_date') or None,
                ))

        return chunks

    def list_documents(self) -> List[Dict]:
        """
        Return a list of unique documents indexed in this collection.
        Each entry includes doc_id, source (filename), and chunk count.
        """
        total = self.collection.count()
        if total == 0:
            return []

        results = self.collection.get(include=["metadatas"])
        metadatas = results.get("metadatas", [])
        ids = results.get("ids", [])

        docs: Dict[str, Dict] = {}
        for meta, chunk_id in zip(metadatas, ids):
            doc_id = meta.get("doc_id", "")
            source = meta.get("source", "") or doc_id
            if doc_id not in docs:
                docs[doc_id] = {
                    "doc_id": doc_id,
                    "source": source,
                    "chunk_count": 0,
                    "document_tier": meta.get("document_tier", ""),
                    "jurisdiction": meta.get("jurisdiction", ""),
                }
            docs[doc_id]["chunk_count"] += 1

        return list(docs.values())

    def delete_document(self, doc_id: str):
        """Delete all chunks belonging to a specific document."""
        results = self.collection.get(where={"doc_id": doc_id}, include=["metadatas"])
        ids_to_delete = results.get("ids", [])
        if ids_to_delete:
            self.collection.delete(ids=ids_to_delete)

    def delete_collection(self):
        """Delete the current collection entirely."""
        self.client.delete_collection(name=self.collection_name)

    def count(self) -> int:
        """Get the number of chunks in the collection."""
        return self.collection.count()


def get_aml_store(index_type: str) -> ChromaStore:
    """
    Factory for AML-specific stores.

    Args:
        index_type: "regulatory" | "internal_policy"

    Returns:
        ChromaStore pointed at the correct AML collection
    """
    if index_type not in ("regulatory", "internal_policy"):
        raise ValueError(f"index_type must be 'regulatory' or 'internal_policy', got: {index_type!r}")
    return ChromaStore(index_type=index_type)


def get_all_collections() -> List[str]:
    """List all available collections."""
    client = chromadb.PersistentClient(path=settings.chroma_persist_directory)
    return [col.name for col in client.list_collections()]


