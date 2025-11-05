"""Generate slice sampling CSV for manual QA."""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

from kg_fusion.paths import EVAL_ROOT, data_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parsed_dir", default=str(data_path("parsed")))
    parser.add_argument("--out_csv", default=str(EVAL_ROOT / "cases" / "slice_sample.csv"))
    parser.add_argument("--per_doc", type=int, default=30)
    args = parser.parse_args()

    parsed_dir = Path(args.parsed_dir)
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    for file in parsed_dir.glob("*.sections.jsonl"):
        lines = [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            continue
        k = min(args.per_doc, len(lines))
        sample = random.sample(lines, k)
        for item in sample:
            rows.append(
                {
                    "doc_id": item["doc_id"],
                    "page_no": item["page_no"],
                    "section_id": item["section_id"],
                    "is_heading": item.get("is_heading", False),
                    "text": item["text"][:80],
                    "bbox": item.get("bbox"),
                    "ok?": "",
                }
            )
    if not rows:
        print("No parsed sections found.")
        return

    with out_csv.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    main()
