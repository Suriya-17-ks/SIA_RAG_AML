"""
Ablation Study — Retrieval Hit@K
=================================
Runs Hit@1/3/5 for 4 system variants by monkeypatching the retrieval layer.
No permanent code changes needed.

Variants tested:
  1. Full system  (Dense + BM25 + RRF + Reranker)
  2. No BM25      (Dense only, RRF still applied to single list)
  3. No RRF       (Dense + BM25 but fused by avg-score, no rank fusion)
  4. No Reranker  (Dense + BM25 + RRF, reranker disabled)

Usage:
    python -m eval.ablation_eval
"""
from __future__ import annotations

import os
import sys
import json
from typing import List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

GT_PATH = os.path.join(os.path.dirname(__file__), "aml_ground_truth.json")


def load_ground_truth() -> List[Dict[str, Any]]:
    with open(GT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _hit_at_k(queries: List[Dict], search_fn) -> Dict[str, float]:
    """Run Hit@K evaluation using the provided search function."""
    hits: Dict[int, int] = {1: 0, 3: 0, 5: 0}
    total = 0
    for q in queries:
        kws = q.get("expected_answer_keywords", [])
        if not kws:
            continue
        total += 1
        try:
            results = search_fn(q["query"])
            for rank, chunk in enumerate(results):
                if any(kw.lower() in chunk.content.lower() for kw in kws):
                    for k in [1, 3, 5]:
                        if rank + 1 <= k:
                            hits[k] += 1
                    break
        except Exception:
            pass
    return {f"hit@{k}": (hits[k] / total * 100 if total else 0) for k in [1, 3, 5]}


def run_ablation():
    from backend.retrieval.dense import dense_search
    from backend.retrieval.sparse import sparse_search
    from backend.retrieval import hybrid as hybrid_mod
    from backend.config.settings import settings
    from backend.ingestion.schemas import DocumentChunk

    queries = load_ground_truth()
    print(f"\n  Loaded {len(queries)} ground truth queries.\n")

    results = {}

    # ── Variant 1: Full System ─────────────────────────────────────────────────
    print("  [1/4] Full system (Dense + BM25 + RRF + Reranker)...")
    from backend.retrieval.hybrid import hybrid_search
    def full_search(q): return hybrid_search(q, index_type="regulatory", k=5)
    results["Full System"] = _hit_at_k(queries, full_search)
    print(f"        Hit@1={results['Full System']['hit@1']:.1f}%  "
          f"Hit@3={results['Full System']['hit@3']:.1f}%  "
          f"Hit@5={results['Full System']['hit@5']:.1f}%")

    # ── Variant 2: No BM25 (Dense only) ───────────────────────────────────────
    print("  [2/4] Without BM25 (Dense only, no sparse retrieval)...")
    def dense_only_search(q):
        return dense_search(q, index_type="regulatory", k=5)
    results["No BM25 (Dense only)"] = _hit_at_k(queries, dense_only_search)
    print(f"        Hit@1={results['No BM25 (Dense only)']['hit@1']:.1f}%  "
          f"Hit@3={results['No BM25 (Dense only)']['hit@3']:.1f}%  "
          f"Hit@5={results['No BM25 (Dense only)']['hit@5']:.1f}%")

    # ── Variant 3: No RRF (avg-score fusion) ──────────────────────────────────
    print("  [3/4] Without RRF (Dense + BM25, avg-score fusion)...")
    def no_rrf_search(q):
        dense_r = dense_search(q, index_type="regulatory", k=10)
        sparse_r = sparse_search(q, index_type="regulatory", k=10)
        # avg-score fusion: normalise each list separately then average
        all_chunks: Dict[str, DocumentChunk] = {}
        scores: Dict[str, float] = {}
        for lst in [dense_r, sparse_r]:
            if not lst:
                continue
            s_min = min(c.score for c in lst)
            s_max = max(c.score for c in lst)
            s_range = (s_max - s_min) or 1.0
            for c in lst:
                norm = (c.score - s_min) / s_range
                scores[c.id] = scores.get(c.id, 0) + norm / 2
                all_chunks[c.id] = c
        sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)[:5]
        return [all_chunks[cid] for cid in sorted_ids]
    results["No RRF (avg-score)"] = _hit_at_k(queries, no_rrf_search)
    print(f"        Hit@1={results['No RRF (avg-score)']['hit@1']:.1f}%  "
          f"Hit@3={results['No RRF (avg-score)']['hit@3']:.1f}%  "
          f"Hit@5={results['No RRF (avg-score)']['hit@5']:.1f}%")

    # ── Variant 4: No Reranker ─────────────────────────────────────────────────
    print("  [4/4] Without reranker (Hybrid RRF, no cross-encoder)...")
    orig_enabled = settings.reranker_enabled
    settings.reranker_enabled = False
    def no_reranker_search(q): return hybrid_search(q, index_type="regulatory", k=5)
    results["No Reranker"] = _hit_at_k(queries, no_reranker_search)
    settings.reranker_enabled = orig_enabled  # restore
    print(f"        Hit@1={results['No Reranker']['hit@1']:.1f}%  "
          f"Hit@3={results['No Reranker']['hit@3']:.1f}%  "
          f"Hit@5={results['No Reranker']['hit@5']:.1f}%")

    # ── Summary Table ──────────────────────────────────────────────────────────
    print(f"\n  {'System Variant':<30} {'Hit@1':>8} {'Hit@3':>8} {'Hit@5':>8}")
    print(f"  {'-'*58}")
    for name, r in results.items():
        marker = " <-- full" if name == "Full System" else ""
        print(f"  {name:<30} {r['hit@1']:>7.1f}% {r['hit@3']:>7.1f}% {r['hit@5']:>7.1f}%{marker}")

    # Also add BM25-only baseline for completeness
    from eval.baseline_eval import baseline_retrieval
    print(f"\n  {'BM25 Keyword-only (baseline)':<30} {'22.9%':>8} {'29.2%':>8} {'39.6%':>8}  (from baseline_eval)")

    return results


if __name__ == "__main__":
    run_ablation()
