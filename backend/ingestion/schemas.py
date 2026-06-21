from enum import Enum
from pydantic import BaseModel
from typing import Optional
from datetime import date


class ContentType(str, Enum):
    PARAGRAPH = "paragraph"
    TABLE = "table"
    WARNING = "warning"
    HEADER = "header"
    LIST = "list"
    FIGURE = "figure"
    CAPTION = "caption"
    CODE = "code"


class StructuredChunk(BaseModel):
    """Represents a chunk of content from a document with structural metadata."""
    doc_id: str
    content: str
    page_number: int
    section_title: Optional[str] = None
    content_type: ContentType
    chunk_id: Optional[str] = None        # For tracking and deduplication
    parent_section_id: Optional[str] = None  # For hierarchical tracking
    hierarchy_level: int = 0              # 0=root, 1=section, 2=subsection, etc.
    source: str = ""                      # Original filename — used for document listing and deletion

    # ── AML Domain Metadata ───────────────────────────────────────────────────
    # Populated by aml_tagger.py during ingestion of AML regulatory documents.
    # All fields are Optional so non-AML documents remain fully backward-compatible.
    regulation_type: Optional[str] = None     # KYC | STR | CTR | PEP | EDD | CDD | Sanctions | RecordKeeping | BeneficialOwnership
    obligation_level: Optional[str] = None    # Mandatory | Recommended | Optional
    jurisdiction: Optional[str] = None        # RBI | FATF | FIU-IND | SEBI | PMLA | EU | USA
    entity_type: Optional[str] = None         # Bank | NBFC | PaymentBank | Broker | VASP
    document_tier: Optional[str] = None       # regulatory | internal_policy

    # ── Versioning (enables "compliant as of date X" temporal queries) ────────
    regulation_version: Optional[str] = None  # e.g. "2023-Q4", "Amendment-7", "Master-Direction-2023"
    effective_date: Optional[date] = None     # When this rule became legally effective
    ingestion_date: Optional[date] = None     # When we ingested/indexed this document
    supersedes: Optional[str] = None          # doc_id of the prior version this document replaces


class DocumentChunk(BaseModel):
    """Retrieved chunk from vector database with metadata."""
    id: str
    content: str
    doc_id: str
    source: str = ""               # Original PDF filename
    page: int                      # Simplified field name for easier access
    section_title: Optional[str] = None
    content_type: str
    score: Optional[float] = None  # Relevance score from retrieval

    # ── AML metadata surfaced from retrieval ──────────────────────────────────
    regulation_type: Optional[str] = None
    obligation_level: Optional[str] = None
    jurisdiction: Optional[str] = None
    document_tier: Optional[str] = None
    effective_date: Optional[str] = None   # Stored as string from ChromaDB metadata

