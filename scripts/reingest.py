"""
scripts/reingest.py
===================
Clears both ChromaDB collections and re-ingests all PDFs from a folder
using the improved pipeline (tiny-filter + heuristic headers + dedup).

Usage:
    python scripts/reingest.py <pdf_folder>
    python scripts/reingest.py uploads/
    python scripts/reingest.py .          # any PDFs in current dir

Options:
    --dry-run    Show what would be ingested without modifying the DB
    --keep-db    Skip the clear step (add new PDFs on top of existing index)
"""

import sys
import os
import argparse
import time
import logging

# ── path setup ───────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.config.settings import settings
from backend.ingestion.ingest_pipeline import ingest_pdf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("reingest")


def clear_collections():
    """Delete and recreate both micro and macro ChromaDB collections."""
    import chromadb
    client = chromadb.PersistentClient(path=settings.chroma_persist_directory)

    for col_name in [settings.collection_micro, settings.collection_macro]:
        try:
            client.delete_collection(col_name)
            logger.info(f"Cleared collection: {col_name}")
        except Exception:
            logger.info(f"Collection not found (skip): {col_name}")


def find_pdfs(folder: str):
    """Recursively find all PDF files under folder."""
    pdfs = []
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, f))
    return sorted(pdfs)


def main():
    parser = argparse.ArgumentParser(
        description="Re-ingest PDFs with improved chunking pipeline"
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=".",
        help="Folder containing PDF files to ingest (default: current dir)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List PDFs that would be ingested without touching the DB",
    )
    parser.add_argument(
        "--keep-db",
        action="store_true",
        help="Skip clearing the DB — add PDFs on top of existing index",
    )
    args = parser.parse_args()

    folder = os.path.abspath(args.folder)
    if not os.path.isdir(folder):
        logger.error(f"Not a directory: {folder}")
        sys.exit(1)

    pdfs = find_pdfs(folder)
    if not pdfs:
        logger.error(f"No PDF files found in: {folder}")
        sys.exit(1)

    logger.info(f"Found {len(pdfs)} PDF(s) in {folder}")
    for p in pdfs:
        logger.info(f"  - {os.path.basename(p)}")

    if args.dry_run:
        logger.info("[DRY RUN] No changes made.")
        return

    # ── Step 1: Clear both collections ───────────────────────────────────────
    if not args.keep_db:
        logger.info("Clearing existing ChromaDB collections...")
        clear_collections()
    else:
        logger.info("--keep-db set: skipping collection clear")

    # ── Step 2: Re-ingest each PDF ────────────────────────────────────────────
    results = []
    total_start = time.perf_counter()

    for i, pdf_path in enumerate(pdfs, 1):
        name = os.path.basename(pdf_path)
        logger.info(f"[{i}/{len(pdfs)}] Ingesting: {name} ...")
        t0 = time.perf_counter()

        try:
            doc_id = ingest_pdf(pdf_path, doc_name=name)
            elapsed = round(time.perf_counter() - t0, 1)
            logger.info(f"  OK  doc_id={doc_id}  ({elapsed}s)")
            results.append((name, "OK", elapsed, doc_id))
        except Exception as e:
            elapsed = round(time.perf_counter() - t0, 1)
            logger.error(f"  FAILED: {e}")
            results.append((name, "FAILED", elapsed, str(e)))

    total = round(time.perf_counter() - total_start, 1)

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("  REINGEST SUMMARY")
    print("=" * 70)
    ok  = [r for r in results if r[1] == "OK"]
    bad = [r for r in results if r[1] != "OK"]
    print(f"  Total : {len(results)}  |  OK: {len(ok)}  |  Failed: {len(bad)}  |  Time: {total}s")
    print()
    for name, status, elapsed, extra in results:
        mark = "OK " if status == "OK" else "ERR"
        print(f"  [{mark}]  {name:<45}  {elapsed:>5}s")
    print("=" * 70)

    if ok:
        print()
        print("  Next: run chunking eval to verify quality improvement")
        print("  $ python eval/run_eval.py --chunking")

    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
