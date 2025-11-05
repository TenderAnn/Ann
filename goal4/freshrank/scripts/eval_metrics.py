"""Evaluate ranking or metadata extraction metrics."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict


def eval_ranking(report_path: Path) -> Dict[str, float]:
    if not report_path.exists():
        raise FileNotFoundError(report_path)
    items = json.loads(report_path.read_text(encoding="utf-8"))
    correctly_sorted = sum(1 for idx, item in enumerate(items) if item.get("expected_rank") == idx)
    accuracy = correctly_sorted / len(items) if items else 0.0
    return {"sorting_accuracy": round(accuracy, 4)}


def load_meta(path: Path) -> Dict[str, dict]:
    mapping: Dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            mapping[payload.get("doc_id")] = payload
    return mapping


def normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return value


def eval_metadata(pred_path: Path, gold_path: Path) -> Dict[str, float]:
    predictions = load_meta(pred_path)
    gold = load_meta(gold_path)
    fields = ["publish_date", "effective_from", "effective_to", "status", "version", "product_code", "doc_type"]
    totals = {field: 0 for field in fields}
    correct = {field: 0 for field in fields}
    for doc_id, gold_row in gold.items():
        pred = predictions.get(doc_id, {})
        for field in fields:
            gold_value = gold_row.get(field)
            pred_value = pred.get(field)
            if field.endswith("date") and field != "status":
                gold_value = normalize_date(gold_value)
                pred_value = normalize_date(pred_value)
            if gold_value is None:
                continue
            totals[field] += 1
            if pred_value == gold_value:
                correct[field] += 1
    metrics = {}
    total_correct = 0
    total_fields = 0
    for field in fields:
        if totals[field] == 0:
            continue
        acc = correct[field] / totals[field]
        metrics[field] = round(acc, 4)
        total_correct += correct[field]
        total_fields += totals[field]
    metrics["overall_accuracy"] = round(total_correct / total_fields if total_fields else 0.0, 4)
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate freshrank tasks")
    parser.add_argument("--task", choices=["ranking", "meta"], required=True)
    parser.add_argument("--report", default="eval/reports/rerank.json")
    parser.add_argument("--pred", default="data/metadata/metadata.jsonl")
    parser.add_argument("--gold", default="data/metadata/metadata_gold.jsonl")
    parser.add_argument("--out", default="eval/reports/metadata_eval.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.task == "ranking":
        metrics = eval_ranking(Path(args.report))
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
    else:
        metrics = eval_metadata(Path(args.pred), Path(args.gold))
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Metadata evaluation saved to {args.out}")


if __name__ == "__main__":
    main()
