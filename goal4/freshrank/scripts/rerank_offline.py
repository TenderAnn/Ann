"""Offline reranking entry point with regulatory ablation."""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from dateutil import parser as date_parser

sys.path.append(str(Path(__file__).resolve().parents[1]))

from freshrank.service.pipeline import RankingPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline reranking with regulatory ablation")
    parser.add_argument("--input", type=Path, default=None, help="Flat candidate list (legacy mode)")
    parser.add_argument("--candidates", type=Path, default=None, help="Query-aware candidate file (JSONL)")
    parser.add_argument("--output", type=Path, default=Path("eval/offline_rerank_output.jsonl"))
    parser.add_argument("--output-off", type=Path, default=None, help="Output path when regulatory=off (optional)")
    parser.add_argument("--regulatory", choices=["on", "off", "both"], default="on")
    parser.add_argument("--ablation-report", type=Path, default=Path("eval/reports/esg_ablation.json"))
    return parser.parse_args()


def load_documents(path: Path) -> List[dict]:
    docs = json.loads(path.read_text(encoding="utf-8"))
    normalize_dates(docs)
    return docs


def load_query_bundles(path: Path) -> List[dict]:
    rows: List[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            normalize_dates(row.get("candidates", []))
            rows.append(row)
    return rows


def normalize_dates(documents: List[dict]) -> None:
    for doc in documents:
        eff = doc.get("effective_date")
        if isinstance(eff, str) and eff:
            try:
                doc["effective_date"] = date_parser.isoparse(eff)
            except ValueError:
                doc["effective_date"] = None


def write_results(path: Path, results, query_mode: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if query_mode:
        with path.open("w", encoding="utf-8") as handle:
            for row in results:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    else:
        path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved rerank results to {path}")


def compute_doc_metrics(documents: List[dict], results: List[dict]) -> dict:
    ref_time = datetime.now(timezone.utc)
    meta = {}
    for doc in documents:
        key = (doc.get("doc_id"), doc.get("chunk_id"))
        eff = doc.get("effective_date")
        age_days = None
        if isinstance(eff, datetime):
            eff_utc = eff if eff.tzinfo else eff.replace(tzinfo=timezone.utc)
            age_days = max(0, (ref_time - eff_utc).days)
        expired = bool(doc.get("expired", False)) or (age_days is not None and age_days > 730)
        meta[key] = {
            "age_days": age_days if age_days is not None else 9999,
            "expired": expired,
            "new": age_days is not None and age_days <= 180,
        }

    pair_total = pair_correct = 0
    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            pair_total += 1
            key_i = (results[i]["doc_id"], results[i].get("chunk_id"))
            key_j = (results[j]["doc_id"], results[j].get("chunk_id"))
            age_i = meta.get(key_i, {}).get("age_days", 9999)
            age_j = meta.get(key_j, {}).get("age_days", 9999)
            if age_i <= age_j:
                pair_correct += 1
    pairwise_accuracy = pair_correct / pair_total if pair_total else 0.0

    top_k = min(10, len(results))
    top_slice = results[:top_k]
    new_in_top = sum(1 for item in top_slice if meta.get((item["doc_id"], item.get("chunk_id")), {}).get("new"))
    expired_in_top = sum(1 for item in top_slice if meta.get((item["doc_id"], item.get("chunk_id")), {}).get("expired"))
    avg_w_reg = sum(item.get("score_breakdown", {}).get("w_regulatory", 0.0) for item in results) / len(results) if results else 0.0

    return {
        "pairwise_recency_accuracy": round(pairwise_accuracy, 4),
        "new_doc_top10_ratio": round(new_in_top / top_k if top_k else 0.0, 4),
        "expired_in_top10_ratio": round(expired_in_top / top_k if top_k else 0.0, 4),
        "avg_w_regulatory": round(avg_w_reg, 4),
    }


def ndcg(scores: List[float], ideal: List[float], k: int = 10) -> float:
    def dcg(values: List[float]) -> float:
        return sum((2 ** rel - 1) / math.log2(idx + 2) for idx, rel in enumerate(values[:k]))

    ideal_scores = sorted(ideal, reverse=True)
    denom = dcg(ideal_scores)
    return 0.0 if denom == 0 else dcg(scores) / denom


def mrr(scores: List[float]) -> float:
    for idx, rel in enumerate(scores, start=1):
        if rel > 0:
            return 1 / idx
    return 0.0


def compute_query_metrics(bundles: List[dict], results: List[dict]) -> dict:
    result_map = {row["query_id"]: row for row in results}
    ref_time = datetime.now(timezone.utc)
    ndcgs = []
    mrrs = []
    new_ratios = []
    expired_ratios = []
    avg_w_regs = []
    for bundle in bundles:
        ranked = result_map.get(bundle["query_id"], {}).get("results", [])
        candidate_meta = {
            (cand["doc_id"], cand.get("chunk_id")): cand for cand in bundle.get("candidates", [])
        }
        gains = [
            candidate_meta.get((item["doc_id"], item.get("chunk_id")), {}).get("label", 0.0)
            for item in ranked
        ]
        ideal = [cand.get("label", 0.0) for cand in bundle.get("candidates", [])]
        ndcgs.append(ndcg(gains, ideal))
        mrrs.append(mrr(gains))
        top_k = min(10, len(ranked))
        top_slice = ranked[:top_k]
        new_hits = 0
        expired_hits = 0
        for item in top_slice:
            meta = candidate_meta.get((item["doc_id"], item.get("chunk_id")), {})
            eff = meta.get("effective_date")
            if isinstance(eff, str) and eff:
                eff_dt = date_parser.isoparse(eff)
            else:
                eff_dt = eff
            if isinstance(eff_dt, datetime):
                eff_dt = eff_dt if eff_dt.tzinfo else eff_dt.replace(tzinfo=timezone.utc)
                age = (ref_time - eff_dt).days
                if age <= 180:
                    new_hits += 1
            if meta.get("expired"):
                expired_hits += 1
        new_ratios.append(new_hits / top_k if top_k else 0.0)
        expired_ratios.append(expired_hits / top_k if top_k else 0.0)
        avg_w_regs.append(sum(item.get("score_breakdown", {}).get("w_regulatory", 0.0) for item in ranked) / len(ranked) if ranked else 0.0)
    return {
        "ndcg@10": round(sum(ndcgs) / len(ndcgs) if ndcgs else 0.0, 4),
        "mrr": round(sum(mrrs) / len(mrrs) if mrrs else 0.0, 4),
        "new_doc_top10_ratio": round(sum(new_ratios) / len(new_ratios) if new_ratios else 0.0, 4),
        "expired_in_top10_ratio": round(sum(expired_ratios) / len(expired_ratios) if expired_ratios else 0.0, 4),
        "avg_w_regulatory": round(sum(avg_w_regs) / len(avg_w_regs) if avg_w_regs else 0.0, 4),
    }


def main() -> None:
    args = parse_args()
    pipeline = RankingPipeline()
    query_mode = args.candidates is not None
    if not args.input and not args.candidates:
        raise SystemExit("Either --input or --candidates must be provided")

    documents = load_documents(args.input) if args.input else []
    query_bundles = load_query_bundles(args.candidates) if query_mode else []

    results_on = results_off = None

    if args.regulatory in {"on", "both"}:
        if query_mode:
            results_on = [
                {
                    "query_id": bundle["query_id"],
                    "query": bundle.get("query"),
                    "results": pipeline.rank(bundle.get("candidates", []), regulatory=True),
                }
                for bundle in query_bundles
            ]
        else:
            results_on = pipeline.rank(documents, regulatory=True)
        write_results(args.output, results_on, query_mode)

    if args.regulatory in {"off", "both"}:
        output_off = args.output_off or Path(str(args.output) + ".off")
        if query_mode:
            results_off = [
                {
                    "query_id": bundle["query_id"],
                    "query": bundle.get("query"),
                    "results": pipeline.rank(bundle.get("candidates", []), regulatory=False),
                }
                for bundle in query_bundles
            ]
        else:
            results_off = pipeline.rank(documents, regulatory=False)
        write_results(output_off, results_off, query_mode)

    if args.regulatory == "both" and args.ablation_report:
        if query_mode:
            metrics = {
                "reg_on": compute_query_metrics(query_bundles, results_on or []),
                "reg_off": compute_query_metrics(query_bundles, results_off or []),
            }
        else:
            metrics = {
                "reg_on": compute_doc_metrics(documents, results_on or []),
                "reg_off": compute_doc_metrics(documents, results_off or []),
            }
        args.ablation_report.parent.mkdir(parents=True, exist_ok=True)
        args.ablation_report.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved ablation report to {args.ablation_report}")


if __name__ == "__main__":
    main()
