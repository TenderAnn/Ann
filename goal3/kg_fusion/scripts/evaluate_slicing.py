"""Compute slicing accuracy from annotated CSV."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from kg_fusion.paths import EVAL_ROOT


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--anno_csv", default=str(EVAL_ROOT / "cases" / "slice_sample.csv"))
    parser.add_argument("--report", default=str(EVAL_ROOT / "reports" / "metrics_slice.json"))
    args = parser.parse_args()

    total = 0
    correct = 0
    per_doc: dict[str, dict[str, int]] = {}

    with Path(args.anno_csv).open(encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            label = row.get("ok?", "").strip()
            if label not in {"0", "1"}:
                continue
            total += 1
            doc_id = row.get("doc_id", "unknown")
            per_doc.setdefault(doc_id, {"t": 0, "c": 0})
            per_doc[doc_id]["t"] += 1
            if label == "1":
                correct += 1
                per_doc[doc_id]["c"] += 1

    accuracy = round((correct / total) * 100, 2) if total else 0.0
    by_doc = {doc: round((vals["c"] / vals["t"]) * 100, 2) for doc, vals in per_doc.items() if vals["t"]}

    report = {
        "total": total,
        "correct": correct,
        "accuracy_pct": accuracy,
        "by_doc": by_doc,
        "target": ">=90%",
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
