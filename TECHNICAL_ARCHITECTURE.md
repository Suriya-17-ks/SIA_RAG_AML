# SIA-RAG: Full Technical Architecture & Design Document

**SIA-RAG — Semantic Intelligence Architecture – Retrieval-Augmented Generation**  
*A Unified Agentic Architecture for Regulatory Question Answering and Automated AML Compliance Gap Analysis*

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Problem Statement & Motivation](#2-problem-statement--motivation)
3. [High-Level System Architecture](#3-high-level-system-architecture)
4. [Component Deep Dive](#4-component-deep-dive)
   - 4.1 [Document Ingestion Pipeline](#41-document-ingestion-pipeline)
   - 4.2 [Intent Router](#42-intent-router)
   - 4.3 [Path A: Regulatory Chatbot](#43-path-a-regulatory-chatbot)
   - 4.4 [Path B: Automated Gap Analyzer](#44-path-b-automated-gap-analyzer)
   - 4.5 [Obligation Knowledge Graph](#45-obligation-knowledge-graph)
   - 4.6 [Monitoring & Evaluation Framework](#46-monitoring--evaluation-framework)
5. [Tech Stack: Choices & Justifications](#5-tech-stack-choices--justifications)
6. [Data Architecture](#6-data-architecture)
7. [API Design](#7-api-design)
8. [Frontend Architecture](#8-frontend-architecture)
9. [Evaluation Results](#9-evaluation-results)
10. [Known Limitations & Future Work](#10-known-limitations--future-work)

---

## 1. Project Overview

SIA-RAG is a research-grade, production-oriented AI compliance platform engineered for the **Anti-Money Laundering (AML) domain** in the Indian financial regulatory ecosystem. It is designed to solve two distinct but related problems on a single unified platform:

- **Regulatory Q&A**: Answer precise, factual questions about AML regulations with cited evidence.
- **Compliance Gap Analysis**: Automatically compare a financial institution's internal AML policy against regulatory obligations and classify each obligation as COVERED, PARTIAL, or MISSING.

The system is implemented as a **LangGraph-orchestrated multi-agent state machine** with a shared document ingestion backbone, two specialized runtime execution paths, and a deterministic hallucination guard — achieving Macro F1 = 1.00 on gap classification and 0.0% hallucination rate in evaluation.

---

## 2. Problem Statement & Motivation

### Why AML Compliance is Hard to Automate

Financial institutions operating under Indian jurisdiction must comply with overlapping regulatory frameworks:
- **PMLA 2002** — Primary statutory law on money laundering
- **RBI KYC Master Direction 2016** — Operational KYC/AML directives
- **FATF 40 Recommendations** — International standard (non-binding but expected)
- **FIU-IND, SEBI** — Additional sector-specific regulators

Manually auditing an institution's internal policy against all obligations requires:
- Deep domain expertise across multiple jurisdictions
- Hours of cross-referencing per audit cycle
- High error rates due to vague or ambiguous policy language
- Continuous re-auditing as regulations evolve

### Why Ordinary RAG Falls Short

Three fundamental challenges prevent out-of-the-box RAG from working in this domain:

**Challenge 1 — Retrieval Quality Degradation**
Standard dense retrieval encodes semantic meaning into vector space. It excels at paraphrase matching but catastrophically fails on:
- Exact numeric thresholds: "₹10 lakh", "30 days", "5 years"
- Acronyms and domain-specific codes: STR, CTR, PEP, VKYC

Pure keyword search (BM25) catches these but misses conceptual paraphrasing, such as a policy saying "beneficial owner identification" when the regulation says "UBO verification."

**Challenge 2 — Hallucinated Evidence**
In a compliance context, a false positive (LLM claiming a policy covers an obligation it doesn't) creates legal liability. Generative LLMs trained on broad corpora will confidently fabricate source citations rather than say "I don't know." Standard RAG has no mechanism to verify whether cited text actually appears in the source document.

**Challenge 3 — Jurisdictional Hierarchy**
AML semantics are jurisdiction-dependent. "Customer Due Diligence" means different things under RBI vs. FATF. A retriever that treats all documents equally may surface an FATF recommendation ahead of a binding RBI mandate — the wrong answer for Indian compliance.

---

## 3. High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        OFFLINE INGESTION                            │
│                                                                     │
│  PDF Documents ──► Docling Parser ──► Dual Chunker ──► Quality Gate │
│                                                   ──► AML Tagger    │
│                                                   ──► Deduplicator  │
│                                                   ──► Embedder      │
│                                                   ──► ChromaDB      │
│                    (4 collections: sentences, sections,             │
│                     aml_regulatory, aml_internal_policy)            │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     ONLINE RUNTIME (LangGraph)                      │
│                                                                     │
│  User Request ──► Intent Router ──┬──► PATH A: Regulatory Chatbot   │
│                                   │      Dense Retrieval            │
│                                   │    + BM25 Sparse Retrieval      │
│                                   │    + RRF Fusion                 │
│                                   │    + Cross-Encoder Reranker     │
│                                   │    + Jurisdiction Weighting     │
│                                   │    + LLM Answer Synthesis       │
│                                   │                                 │
│                                   └──► PATH B: Gap Analyzer         │
│                                          Regulatory Chunk Fetcher   │
│                                        + Internal Policy Fetcher    │
│                                        + LLM Entailment Judge       │
│                                        + Evidence Hallucination Guard│
│                                        + Structured Gap Report      │
└─────────────────────────────────────────────────────────────────────┘
```

The system is divided into two distinct phases:
1. **Offline Ingestion** — Runs once (or on new document upload). Parses, chunks, tags, deduplicates, embeds, and stores documents.
2. **Online Runtime** — Triggered per user request. Routes intent and executes one of two pipelines.

---

## 4. Component Deep Dive

### 4.1 Document Ingestion Pipeline

**File:** `backend/ingestion/`

#### 4.1.1 PDF Parser (`pdf_parser.py`)

**What it does:** Converts raw PDF regulatory documents into structured, layout-aware text with preserved hierarchy.

**Technology chosen: Docling**

| Alternative | Why Rejected |
|---|---|
| PyPDF2 | Extracts raw text; destroys all formatting, tables, headers vanish |
| pdfplumber | Better than PyPDF2 but no ML-based layout detection |
| Adobe PDF Extract API | Paid, cloud dependency, not suitable for sensitive compliance docs |
| **Docling** ✓ | ML-based layout model detects semantic boundaries, preserves document hierarchy |

Docling's ML layout model classifies each page region (heading, body, table, caption) before extraction. This is critical because regulatory documents like the PMLA are structured as numbered chapters, sections, and sub-clauses — structure that carries semantic meaning (a section header indicates the scope of the clauses below it).

**Heuristic fallback:** If Docling's layout model isn't confident, a custom heuristic promotes a text block to a section header if:
- Uppercase-to-lowercase character ratio > 70%
- Token count ≤ 10 words

---

#### 4.1.2 Dual-Granularity Chunker (`chunker.py`)

**What it does:** Slices parsed documents into two sizes of text chunks simultaneously.

**Two chunk types:**
- **Micro chunks** (sentence/paragraph level, 10–256 words): Used for dense retrieval in the chatbot. Precise, specific context windows.
- **Macro chunks** (section-level aggregations, 256+ words): Provide broader context for the gap analyzer where entire regulatory sections must be evaluated.

**Why dual granularity?**

Different queries require different context windows:
- *"What is the cash transaction reporting threshold?"* → needs a micro chunk with the exact sentence
- *"Does our policy cover AML transaction monitoring obligations?"* → needs a macro chunk with the full section context

All standard RAG implementations use a single chunk size. Dual granularity is the key to handling both precision Q&A and document-level entailment with the same indexed corpus.

**Quality Gate:** Any chunk with fewer than 10 tokens is discarded. Sub-10-token chunks are typically table headers, page numbers, or formatting artifacts that add noise to retrieval.

---

#### 4.1.3 Hybrid AML Tagger (`aml_tagger.py`)

**What it does:** Enriches every chunk with structured AML metadata before indexing.

Each chunk is tagged with:
- `regulation_type`: KYC / STR / CTR / PEP / EDD / AML_GENERAL
- `jurisdiction`: RBI / PMLA / FATF / FIU_IND / SEBI
- `obligation_level`: MANDATORY / RECOMMENDED / INFORMATIONAL
- `document_tier`: STATUTORY_LAW / REGULATORY_DIRECTIVE / INTERNATIONAL_STANDARD

**Two-pass hybrid strategy:**

**Pass 1 — Deterministic Rule Engine (O(1) per chunk):**
A keyword taxonomy matching system classifies clear-cut cases instantly. For example:
- Chunk contains "Know Your Customer" or "KYC" → `regulation_type = KYC`
- Source filename matches "PMLA" → `jurisdiction = PMLA`, `document_tier = STATUTORY_LAW`
- Contains "shall" or "must" → `obligation_level = MANDATORY`

Result: ~73% of chunks classified at zero LLM inference cost.

**Pass 2 — LLM Classification (for ambiguous chunks):**
The remaining ~27% of chunks that don't match simple keyword patterns are sent to LLaMA 3.3 70B in parallelized batches for fine-grained classification.

**Why this hybrid approach?**

| Pure Rule Engine | Pure LLM Tagger | Hybrid (Ours) |
|---|---|---|
| O(1), no cost | High accuracy | O(1) for 73%, LLM for 27% |
| 72–85% accuracy on edge cases | ~4x inference overhead | 85–93% accuracy |
| Misses paraphrased expressions | Overkill for "shall" → MANDATORY | Near-LLM accuracy at fraction of cost |

---

#### 4.1.4 Near-Duplicate Deduplication

**What it does:** Removes redundant chunks before indexing to keep ChromaDB clean.

**Method:** All chunks are embedded. Per-document cosine similarity is computed:
```
cos(θ) = Â · B̂
```
Chunks with cosine similarity > 0.95 to any previously accepted chunk from the same document are discarded.

**Why 0.95 threshold?** Regulatory documents frequently repeat the same obligation verbatim in different sections (e.g., "the Reporting Entity shall file an STR" appears in 3 different sections of the PMLA). Without deduplication, these chunks would dominate retrieval results, wastefully consuming the top-K slots.

---

#### 4.1.5 Embedding & Storage

**Embedding Model: `all-MiniLM-L6-v2`**

| Alternative | Why Rejected / Why Chosen |
|---|---|
| OpenAI `text-embedding-3-large` | Paid API, every query costs money, data leaves the system |
| `bge-large-en-v1.5` | 1024-dim, high RAM requirement for local inference |
| `all-mpnet-base-v2` | 768-dim, slower inference than MiniLM |
| **`all-MiniLM-L6-v2`** ✓ | 384-dim, 22M params, runs fully locally, 5x faster than mpnet, 80% of accuracy |

The model runs locally via `sentence-transformers`. This means:
- No API costs for embedding (regulatory docs can be large)
- Sensitive compliance data never leaves the server
- Sub-second embedding inference on CPU

**Vector Store: ChromaDB**

Four distinct collections are maintained:

| Collection | Contents | Used By |
|---|---|---|
| `documents_sentences` | Generic micro chunks (all uploaded docs) | Chatbot Path A |
| `documents_sections` | Generic macro chunks (all uploaded docs) | Gap Analyzer Path B |
| `aml_regulatory` | AML-specific regulatory obligation chunks | Gap Analyzer Path B |
| `aml_internal_policy` | AML-specific internal policy chunks | Gap Analyzer Path B |

**Why separate AML-specific collections?**

The Gap Analyzer needs to specifically fetch regulatory obligations and then match them against internal policies. If everything were in one collection, retrieval would mix regulatory and policy chunks together, making the entailment comparison impossible. Separate collections allow targeted, deterministic fetching of obligations.

---

### 4.2 Intent Router

**What it does:** Classifies each incoming user request and dispatches it to Path A or Path B.

**Two-stage routing:**

**Stage 1 — Regex Preprocessing:**
A set of fast regex patterns detect obvious intents before touching the LLM:
- Contains "gap" or "analyze policy" or "compare" → likely Gap Analyzer
- Contains a question mark or "what", "how", "when", "why" → likely Chatbot

**Stage 2 — LRU-Cached LLM Classification:**
For ambiguous requests, the LLM classifies the intent. The last N classifications are cached in an LRU cache keyed on the request text. This means repeated or similar queries (common in compliance workflows) skip LLM inference entirely.

**Design philosophy:** Regex is O(1) and free. LLM classification is ~200ms and costs inference. The two-stage approach front-loads the cheap check, saving LLM calls for genuinely ambiguous cases.

---

### 4.3 Path A: Regulatory Chatbot

**Goal:** Given a regulatory question, retrieve the most relevant chunks and synthesize a cited, factually grounded answer.

#### Step 1 — Parallel Hybrid Retrieval

Dense and sparse retrieval execute **concurrently** via a shared thread pool, not sequentially.

**Dense Retrieval:**
The query is embedded with `all-MiniLM-L6-v2` and performs approximate nearest-neighbor search in ChromaDB using cosine distance. This captures semantic/paraphrase relationships.

**Sparse Retrieval (BM25):**
The Okapi BM25 algorithm scores each chunk against the query using term frequency and inverse document frequency:

```
BM25(D,Q) = Σ IDF(qᵢ) · [f(qᵢ,D) · (k₁+1)] / [f(qᵢ,D) + k₁(1 - b + b·|D|/avgdl)]
```

Parameters: k₁ = 1.2, b = 0.75 (standard BM25 defaults).

This catches exact keyword matches — critical for numeric thresholds and regulatory codes.

**Why parallel execution?**
Sequential dense → sparse retrieval would add ~40–50ms of total latency per query. Running both concurrently cuts retrieval latency by ~40–50% with no correctness trade-off.

#### Step 2 — Reciprocal Rank Fusion (RRF)

Dense and sparse retrieve 2k candidates each. RRF merges both ranked lists:

```
RRF(d) = Σ_{r ∈ {dense, sparse}} 1 / (60 + rankᵣ(d))
```

**Why RRF over score averaging?**

| Score Averaging | Reciprocal Rank Fusion |
|---|---|
| Requires normalized scores (BM25 is unbounded, cosine is [0,1]) | Only uses rank position, score magnitude irrelevant |
| Sensitive to outlier scores | Robust to outliers by design |
| Fails when score distributions are incompatible | Practically outperforms individual methods in specialized domains |

The constant k=60 is the standard RRF smoothing constant from the original SIGIR 2009 paper. It prevents very high-ranked documents from dominating unfairly.

#### Step 3 — Jurisdiction-Aware Cross-Encoder Reranking

**Model: `ms-marco-MiniLM-L-6-v2`** (23M parameters, trained on MS-MARCO relevance dataset)

The cross-encoder takes the (query, chunk) pair together and computes relevance through **full mutual attention** — unlike bi-encoders that embed query and document independently:

```
f(q, d) = W^T · CLS(q ⊕ d)
```

This captures fine-grained relevance signals (e.g., whether "customer" in the query refers to the same entity as "reporting entity" in the chunk) that bi-encoders cannot.

**Jurisdictional blending:**

After cross-encoder scores, a jurisdiction authority weight is blended:

```
Score_final = 0.8 · S_semantic + 0.2 · W_jurisdiction
```

Where:
- W_jur = 1.0 for PMLA / RBI / FIU-IND (binding Indian national law)
- W_jur = 0.6 for FATF / EU (international, non-binding in India)

**Justification:** In Indian financial compliance, a Statutory Law (PMLA) obligation supersedes an international guideline (FATF). The 80/20 blend ensures semantic relevance remains dominant while national authority breaks ties between equally relevant chunks from different jurisdictions.

#### Step 4 — LLM Answer Synthesis

The top-K reranked chunks are formatted into a structured prompt for LLaMA 3.3 70B. The LLM is instructed to:
- Only answer using information present in the provided chunks
- Cite specific chunks by source and section
- State uncertainty if chunks do not contain enough information

**Why LLaMA 3.3 70B via Groq?**

| Model Option | Why Rejected / Why Chosen |
|---|---|
| GPT-4o (OpenAI) | High cost, data leaves system, ~15% hallucination rate without grounding |
| Claude 3.5 Sonnet | Proprietary, high cost |
| Mistral 7B (local) | Too small for complex legal reasoning |
| LLaMA 3.3 70B (Groq) ✓ | Open weights, Groq provides ultra-low latency inference (~300ms), strong instruction following |

---

### 4.4 Path B: Automated Gap Analyzer

**Goal:** For each regulatory obligation in `aml_regulatory`, determine whether the internal policy satisfies it.

#### Step 1 — Regulatory Obligation Fetching

All chunks from the `aml_regulatory` ChromaDB collection are fetched. These are the obligations that the internal policy must be checked against.

#### Step 2 — Internal Policy Retrieval

For each regulatory obligation chunk, a targeted dense retrieval is performed against `aml_internal_policy` to find the most relevant internal policy excerpt.

#### Step 3 — LLM Entailment Judge

The LLM judge receives:
- The regulatory obligation text
- The best-matching internal policy excerpt

It classifies the relationship using an explicit three-step decision rule:

1. **MISSING** — The internal policy has zero mention of the required concept.
2. **COVERED** — The internal policy explicitly satisfies all requirements: correct thresholds, scope, and specific values.
3. **PARTIAL** — The policy addresses the topic but is incomplete: vague language, wrong specific values (e.g., says "large amounts" instead of "₹10 lakh"), or partial scope.

**Why a precision-engineered prompt matters:**

A naive judge prompt ("Does this policy cover this regulation? Answer COVERED/PARTIAL/MISSING") achieved Macro F1 = **0.516** on the PARTIAL class (the hardest boundary case). The precision-engineered prompt with the explicit three-step checklist, examples of each class, and instructions to check thresholds and scope raised Macro F1 to **1.00**.

The PARTIAL class is the hardest because it requires fine-grained reasoning: the policy may mention KYC but with a 45-day timeline when the regulation mandates 30 days. A naive prompt misses this distinction.

**LLM settings for the judge:** temperature = 0.0 (deterministic, no creative variance in compliance judgments).

#### Step 4 — Evidence Hallucination Guard

After the LLM verdict, the judge is also asked to quote the specific evidence from the policy text that supports the verdict.

The guard performs a **deterministic substring check**:
```python
evidence_valid = cited_evidence in policy_excerpt
```

If the quoted evidence does not appear verbatim in the policy text, the citation is marked as invalid and rejected from the report. This is a hard, non-negotiable constraint.

**Why deterministic substring matching (not semantic similarity)?**

Semantic similarity would allow the LLM to cite a paraphrase that isn't in the source text — which is exactly what hallucination looks like. Only exact substring matching guarantees the cited text is genuinely present.

**Result:** 0.0% hallucination rate. Every citation in the final report is verifiable by a human auditor.

#### Step 5 — Compliance Score Calculation

A composite compliance score is computed per obligation:

```
Score_i = (0.7 · S_sim + 0.3 · S_cite) × W_reg
```

Where:
- `S_sim` = cosine similarity between regulation chunk and policy chunk (0.0–1.0)
- `S_cite` = citation verification binary (1.0 if evidence verified, 0.0 if hallucinated)
- `W_reg` = regulatory severity weight (1.0 for MANDATORY, 0.7 for RECOMMENDED, 0.4 for INFORMATIONAL)

#### Step 6 — Gap Report Generation

The system emits a structured report containing:
- Per-obligation verdict (COVERED / PARTIAL / MISSING)
- Verified evidence quotes
- Compliance score per obligation
- Overall compliance percentage
- Remediation recommendations for PARTIAL and MISSING items

---

### 4.5 Obligation Knowledge Graph

**File:** `backend/graph/obligation_graph.py`

**Technology: NetworkX (Python)**

The ingested regulatory obligations are organized as a directed graph where edges represent:
- `supersedes` — newer RBI circular supersedes older guidance
- `requires` — one obligation requires another (e.g., EDD requires CDD)
- `related_to` — topically related obligations

**Current use:** Graph-based transitive analysis is implemented as an enhancement layer. Future work will use this graph to detect hidden compliance risks — for example, if an institution covers obligation A but regulation B both supersedes A and adds new requirements, the graph can surface the new gap automatically.

**Why NetworkX?** Lightweight, pure-Python, sufficient for the current graph scale (~623 nodes). Neo4j or similar would be overkill for a research prototype and adds operational complexity.

---

### 4.6 Monitoring & Evaluation Framework

**Directory:** `backend/monitoring/` and `eval/`

The evaluation framework computes:
- **Hit@K** (K=1, 3, 5) — retrieval correctness on 48 ground-truth queries
- **Macro F1** — gap classification quality on 13 annotated test cases
- **Hallucination Rate** — fraction of cited evidence that fails the substring guard
- **Judge Latency** — median time per gap classification

Ground truth was manually annotated with answer keywords (for retrieval evaluation) and COVERED/PARTIAL/MISSING labels (for gap classification). There are 50 total evaluation queries spanning 6 intent types (fact, lookup, gap, cross-jurisdiction, remediation, summary) at Easy/Medium/Hard difficulty levels.

---

## 5. Tech Stack: Choices & Justifications

### Orchestration: LangGraph

| Alternative | Why Rejected |
|---|---|
| LangChain sequential chains | Linear execution; no conditional branching or state machine logic |
| Custom Python orchestration | Reinventing the wheel; no built-in state management or checkpointing |
| AutoGen / CrewAI | Multi-agent debate frameworks; overkill, less deterministic for compliance use cases |
| **LangGraph** ✓ | Directed acyclic graph (DAG) with typed state; each node is a pure function; conditional edges enable intent-based routing; built-in persistence via checkpointing |

LangGraph's state machine model maps cleanly onto the SIA-RAG architecture: each pipeline stage is a node, and the intent router is an edge condition. This structure makes the codebase auditable — the execution path is visible and deterministic.

---

### Backend Framework: FastAPI (Python)

| Alternative | Why Rejected |
|---|---|
| Flask | Synchronous by default; no native async support for concurrent retrieval |
| Django | Full MVC framework; massive overhead for an API-only backend |
| FastAPI ✓ | Async-native, automatic OpenAPI docs, Pydantic validation, type hints throughout |

FastAPI's async support is critical for the parallel retrieval step in Path A: dense and sparse retrieval run concurrently using `asyncio` or thread pools.

---

### LLM Provider: Groq API (LLaMA 3.3 70B)

| Alternative | Why Rejected |
|---|---|
| OpenAI GPT-4o | High cost, ~$15/million output tokens; compliance data leaves the organization |
| Anthropic Claude | Proprietary, high cost at scale |
| Ollama (local LLaMA) | 70B model requires 40+ GB VRAM to run at useful speed |
| **Groq (LLaMA 3.3 70B)** ✓ | LPU-accelerated inference, ~300ms latency, open-weights model, competitive cost |

Groq's Language Processing Unit (LPU) provides sub-second inference on a 70B parameter model — impossible on standard GPU inference at this parameter count without significant hardware.

---

### Vector Database: ChromaDB

| Alternative | Why Rejected |
|---|---|
| Pinecone | Managed cloud service; sensitive regulatory data leaving the server |
| Weaviate | More complex operational overhead; overkill for this scale |
| FAISS | No persistent storage; in-memory only unless manually serialized |
| Qdrant | Good alternative; ChromaDB chosen for simpler Python-native API and local persistence |
| **ChromaDB** ✓ | Local persistent storage, Python-native, simple collection management, supports metadata filtering |

ChromaDB's metadata filtering capability is used by the jurisdiction-aware retriever to pre-filter chunks by jurisdiction before running cosine similarity search — a key performance optimization.

---

### Sparse Retrieval: rank_bm25

**Why not Elasticsearch?** For a research prototype indexing ~3,800 total chunks, spinning up an Elasticsearch cluster adds operational complexity with no benefit. `rank_bm25` is a pure Python BM25 implementation that runs in-process, requires no server, and adds ~2ms overhead.

---

### Cross-Encoder Reranker: ms-marco-MiniLM-L-6-v2

| Alternative | Why Rejected |
|---|---|
| `ms-marco-MiniLM-L-12-v2` | 12-layer variant; 2x slower with marginal accuracy gain on short chunks |
| `bge-reranker-large` | 1.3B params; high inference cost locally |
| `ms-marco-MiniLM-L-6-v2` ✓ | 6-layer, 23M params, 33ms/pair, trained on 500K MS-MARCO relevance pairs |

The model was trained specifically on passage relevance — the exact task of reranking retrieved chunks for a query.

---

### PDF Parsing: Docling (IBM)

| Alternative | Why Rejected |
|---|---|
| PyPDF2 / pypdf | Pure text extraction; destroys headers, tables, structure |
| pdfminer.six | Low-level, requires manual structure reconstruction |
| Unstructured.io | Good but outputs untyped elements; requires parsing |
| **Docling** ✓ | ML layout detection (DocLayNet model), preserves hierarchical structure as typed elements |

---

### Frontend: Next.js + Tailwind CSS

| Alternative | Why Rejected |
|---|---|
| Pure HTML/JS | Not suitable for a data-rich dashboard with real-time updates |
| React (CRA) | Slower bundler; no SSR; Next.js is the modern standard |
| Vue.js | Smaller ecosystem for the compliance dashboard componentization |
| **Next.js + Tailwind** ✓ | App router for SSR/SSG, Tailwind for rapid utility-first styling, React ecosystem for component libraries |

---

### Containerization: Docker + Docker Compose

Backend and frontend are containerized separately and orchestrated via Docker Compose. This ensures reproducible deployment regardless of host OS and makes it trivial to scale either service independently.

---

## 6. Data Architecture

### ChromaDB Collection Schema

**`aml_regulatory` collection:**
```
document_id   : str
text          : str          # chunk text
embedding     : float[384]   # all-MiniLM-L6-v2 vector
metadata:
  source_file   : str        # origin PDF filename
  chunk_type    : micro|macro
  regulation_type: KYC|STR|CTR|PEP|EDD|AML_GENERAL
  jurisdiction  : PMLA|RBI|FATF|FIU_IND|SEBI
  obligation_level: MANDATORY|RECOMMENDED|INFORMATIONAL
  document_tier : STATUTORY_LAW|REGULATORY_DIRECTIVE|INTERNATIONAL_STANDARD
  section_header: str        # parent section title
  page_number   : int
```

**`aml_internal_policy` collection:**
Same schema. `jurisdiction` field reflects the institution's internal context.

### Dataset Statistics

| Metric | Value |
|---|---|
| Regulatory PDFs ingested | 3 (FATF 40 Recs, RBI KYC MD, PMLA 2002) |
| Internal Policy PDFs | 1 |
| Total pages | ~369 |
| `aml_regulatory` chunks | 623 |
| `aml_internal_policy` chunks | 63 |
| `documents_sentences` chunks | 3,078 |
| `documents_sections` chunks | 84 |
| Average chunk size | 39 words |
| Chunk size range | 10–256 words |

---

## 7. API Design

**Base URL:** `http://localhost:8000`

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/chat` | POST | Send a message to the Regulatory Chatbot |
| `/api/upload` | POST | Upload a document for ingestion (requires `doc_type` param) |
| `/api/gap-analyze` | POST | Trigger gap analysis against uploaded internal policy |
| `/api/collections` | GET | List all active ChromaDB collections and chunk counts |
| `/api/health` | GET | Health check |

**`doc_type` parameter on `/api/upload`:**
- `regulatory` → routes to `aml_regulatory` collection
- `internal_policy` → routes to `aml_internal_policy` collection
- `general` → routes to `documents_sentences` and `documents_sections`

This routing ensures the Gap Analyzer's targeted fetching works correctly.

---

## 8. Frontend Architecture

The frontend is a Next.js application located in `frontend-next/`.

**Key pages:**
- `/` — Landing page with system overview and live status
- `/chat` — Regulatory chatbot interface with citation cards
- `/gap-analyzer` — Policy upload and audit report viewer

**State management:** React Context API (no Redux needed at this scale)

**Key UI components:**
- `ChatInterface` — Real-time streaming chat window
- `CitationCard` — Displays retrieved chunk with source document, section, and jurisdiction badge
- `GapReportTable` — Obligation × Status matrix with color coding (green/yellow/red)
- `EvidencePanel` — Shows verified policy evidence quote for each obligation
- `ComplianceScoreGauge` — Radial gauge showing overall compliance percentage

---

## 9. Evaluation Results

### Retrieval Performance (48 ground-truth queries)

| System Variant | Hit@1 | Hit@3 | Hit@5 |
|---|---|---|---|
| BM25 keyword-only (baseline) | 22.9% | 29.2% | 39.6% |
| Dense only (no BM25) | 52.1% | 60.4% | 75.0% |
| Dense + BM25, avg-score fusion | 58.3% | 68.8% | 75.0% |
| **Full System (Dense+BM25+RRF+Reranker)** | **60.4%** | **70.8%** | **72.9%** |

**Critical insight:** Hit@1 is the most important metric in compliance auditing. The correct regulatory clause must appear first, not buried at position 4. The full system achieves Hit@1 = 60.4% vs. 52.1% for dense-only — a **+16% improvement** at the position that matters most.

### Gap Classification Performance (13 annotated test cases)

| Class | Precision | Recall | F1 |
|---|---|---|---|
| COVERED | 100% | 100% | 100% |
| PARTIAL | 100% | 100% | 100% |
| MISSING | 100% | 100% | 100% |
| **Macro F1** | | | **1.00** |
| Hallucination Rate | | | **0.0%** |
| Avg. Judge Latency | | | 0.33s/query |

### AML Tagger Accuracy

| Tag Field | Rule Engine | LLM Only | Hybrid (Ours) |
|---|---|---|---|
| Regulation Type | 78% | 94% | 91% |
| Jurisdiction | 85% | 96% | 93% |
| Obligation Level | 72% | 88% | 85% |

The hybrid tagger processes 73% of chunks at O(1) cost, achieving near-LLM accuracy (93% vs. 96% on jurisdiction) with a fraction of the inference overhead.

---

## 10. Known Limitations & Future Work

### Current Limitations

1. **Small evaluation corpus:** 13 annotated gap-classification test cases is a proof-of-concept scale. Future expansion to 100+ expert-annotated cases is needed.
2. **PDF quality dependency:** Scanned historical circulars (image-based PDFs) degrade Docling parsing quality. OCR pre-processing is not currently implemented.
3. **Regulatory coverage:** Only 3 regulatory sources ingested. FIU-IND STR guidelines, RBI CTR circulars, and SEBI AML circulars would reduce the 27.1% miss rate at Hit@5.
4. **Single-institution policy:** Gap analysis is currently designed for one internal policy at a time. Multi-entity comparison is not implemented.

### Planned Future Work

1. **Transitive gap detection via ObligationGraph:** Use the NetworkX graph to detect hidden gaps — obligations where policy indirectly covers A, but a newer regulation B supersedes A with additional requirements.
2. **Agentic multi-hop reasoning:** For complex cross-jurisdictional queries that require reasoning across multiple retrieved chunks.
3. **Incremental ingestion:** Real-time monitoring of regulatory update feeds (RBI press releases, FIU-IND circulars) with automatic diff-based re-ingestion.
4. **Expanded ground truth:** Crowdsourcing annotations from domain expert compliance officers.
5. **OCR integration:** Tesseract or Google Document AI for scanned legacy circulars.

---

*Document version: 1.0 | Last updated: March 2026*  
*Authors: A Allan, Suriya K S | Supervisor: Dr. Simhadri Ravishankar | Amrita School of Engineering, Chennai*
