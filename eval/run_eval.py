"""
eval/run_eval.py
================
Master evaluation runner — executes all three evaluators in sequence
and prints a consolidated terminal summary.

Also saves a timestamped history snapshot to eval/history/.

Run:
    python eval/run_eval.py              # all evaluators
    python eval/run_eval.py --chunking   # chunking only
    python eval/run_eval.py --retrieval  # retrieval only
    python eval/run_eval.py --router     # router only
"""

import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
HISTORY_DIR = os.path.join(os.path.dirname(__file__), "history")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

THRESHOLDS = {
    "recall":       0.80,
    "mrr":          0.60,
    "hit1":         0.60,
    "router_acc":   0.85,
    "coherence":    0.60,
    "redundancy":   5.0,   # pct — below this is good
    "separation_lo": 0.20,
    "separation_hi": 0.90,
}


def badge(value, threshold, lower_better=False):
    if value is None:
        return "⚪"
    if lower_better:
        return "🟢" if value <= threshold else ("🟡" if value <= threshold * 2 else "🔴")
    return "🟢" if value >= threshold else ("🟡" if value >= threshold * 0.75 else "🔴")


def load_json(filename):
    path = os.path.join(RESULTS_DIR, filename)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def run_chunking():
    print("\n" + "="*60)
    print("  [1/3] CHUNKING EVALUATION")
    print("="*60)
    from eval.chunking_eval import run
    run()


def run_retrieval():
    print("\n" + "="*60)
    print("  [2/3] RETRIEVAL EVALUATION")
    print("="*60)
    from eval.retrieval_eval import run
    return run()


def run_router():
    print("\n" + "="*60)
    print("  [3/3] ROUTER EVALUATION")
    print("="*60)
    from eval.router_eval import run
    return run()


def print_final_summary():
    """Print consolidated dashboard-style summary from saved JSON reports."""
    chunking  = load_json("chunking_report.json")
    retrieval = load_json("retrieval_report.json")
    router    = load_json("router_report.json")

    print("\n")
    print("+" + "="*58 + "╗")
    print("|" + "      SIA-RAG EVALUATION SUMMARY".center(58) + "|")
    print("+" + "="*58 + "+")

    # -- Retrieval --
    if retrieval:
        pipelines = retrieval.get("pipelines", {})
        print("|" + "  RETRIEVAL".ljust(58) + "|")
        print("|" + f"  {'Pipeline':<20} {'Recall@5':>8} {'Hit@1':>7} {'MRR':>7} {'Latency':>9}".ljust(58) + "|")
        print("|" + f"  {'-'*54}".ljust(58) + "|")
        for key, p in pipelines.items():
            r  = p["recall_at_k"];  rb = badge(r, THRESHOLDS["recall"])
            h1 = p["hit_at_1"];    h1b = badge(h1, THRESHOLDS["hit1"])
            m  = p["mrr"];          mb = badge(m, THRESHOLDS["mrr"])
            lat = f"{p['latency_avg_ms']:.0f}ms"
            label = f"{p['method']}-{p['granularity']}"
            line = f"  {label:<20} {rb} {r:.3f}  {h1b} {h1:.3f}  {mb} {m:.3f}  {lat}"
            print("|" + line.ljust(58) + "|")

        # Fusion impact
        for key, fi in retrieval.get("fusion_impact", {}).items():
            gran = key.split("_")[-1]
            line = f"  Fusion ({gran}): Δ={fi['improvement']:+.3f}  [{fi['verdict']}]"
            print("|" + line.ljust(58) + "|")

        zi = retrieval.get("zoom_out", {})
        line = f"  Zoom-out: {zi.get('trigger_rate_pct', 0):.1f}% triggered  |  {zi.get('improvement_rate_pct', 0):.1f}% improved"
        print("|" + line.ljust(58) + "|")
        print("+" + "="*58 + "+")

    # -- Router --
    if router:
        oa  = router.get("overall_accuracy", 0)
        pv  = router.get("preprocessor_vs_llm", {})
        fia = router.get("field_accuracy", {})
        print("|" + "  ROUTER".ljust(58) + "|")
        line = f"  Overall Accuracy: {badge(oa, THRESHOLDS['router_acc'])} {oa:.1%}   (intent={fia.get('intent', 0):.0%}  retrieval={fia.get('retrieval', 0):.0%}  gran={fia.get('granularity', 0):.0%})"
        print("|" + line.ljust(58) + "|")
        line = f"  Preprocessor resolved {pv.get('preprocessor_pct', 0):.1f}%  |  LLM needed {pv.get('llm_pct', 0):.1f}%"
        print("|" + line.ljust(58) + "|")
        line = f"  Est. cost saved/100 queries: ${pv.get('cost_saved_per_100_usd', 0):.4f}"
        print("|" + line.ljust(58) + "|")
        print("+" + "="*58 + "+")

    # -- Chunking --
    if chunking:
        print("|" + "  CHUNKING".ljust(58) + "|")
        for col in ["micro", "macro"]:
            data = chunking.get(col, {})
            if not data:
                continue
            ic  = data.get("intra_coherence", {}).get("avg")
            rd  = data.get("redundancy", {}).get("redundancy_pct")
            sep = data.get("inter_separation", {}).get("avg")
            td  = data.get("token_distribution", {})
            cob = badge(ic, THRESHOLDS["coherence"])
            rdb = badge(rd, THRESHOLDS["redundancy"], lower_better=True)
            line = (f"  {col.upper():<6}  coherence={cob} {str(ic):>5}  "
                    f"redundancy={rdb} {str(rd):>4}%  "
                    f"tokens avg={td.get('avg')}")
            print("|" + line.ljust(58) + "|")

        si = chunking.get("cross_collection", {}).get("section_integrity", {})
        if si.get("avg_integrity") is not None:
            line = f"  Section Integrity: {si['avg_integrity']:.2%}  {si.get('flag', '')}"
            print("|" + line.ljust(58) + "|")

    print("+" + "="*58 + "╝")
    print()


def save_history_snapshot():
    """Save current results as a timestamped history entry."""
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    snapshot = {
        "run_id":       ts,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
    for name in ["chunking_report", "retrieval_report", "router_report"]:
        data = load_json(f"{name}.json")
        if data:
            snapshot[name] = data

    out_path = os.path.join(HISTORY_DIR, f"run_{ts}.json")
    with open(out_path, "w") as f:
        json.dump(snapshot, f, indent=2)
    print(f"  [dir]  History snapshot -> {out_path}\n")


def main():
    parser = argparse.ArgumentParser(description="SIA-RAG Evaluation Runner")
    parser.add_argument("--chunking",  action="store_true", help="Run only chunking eval")
    parser.add_argument("--retrieval", action="store_true", help="Run only retrieval eval")
    parser.add_argument("--router",    action="store_true", help="Run only router eval")
    args = parser.parse_args()

    # If no flags -> run all
    run_all = not (args.chunking or args.retrieval or args.router)

    if args.chunking or run_all:
        run_chunking()
    if args.retrieval or run_all:
        run_retrieval()
    if args.router or run_all:
        run_router()

    if run_all:
        print_final_summary()
        save_history_snapshot()


if __name__ == "__main__":
    main()
