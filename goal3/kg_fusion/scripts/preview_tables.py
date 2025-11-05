"""Preview first rows of extracted tables as CSV."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from kg_fusion.paths import EVAL_ROOT, data_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", default=str(data_path("tables")))
    parser.add_argument("--out_csv", default=str(EVAL_ROOT / "reports" / "table_preview.csv"))
    parser.add_argument("--head_rows", type=int, default=10)
    args = parser.parse_args()

    tables_dir = Path(args.tables)
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    for file in sorted(tables_dir.glob("*.tables.jsonl")):
        with file.open(encoding="utf-8") as fh:
            for line in fh:
                table = json.loads(line)
                doc_id = table["doc_id"]
                table_id = table["table_id"]
                page_no = table["page_no"]
                n_rows = table.get("n_rows", 0) or 0
                n_cols = table.get("n_cols", 0) or 0
                grid = [["" for _ in range(n_cols)] for _ in range(n_rows)]
                for cell in table.get("cells", []):
                    r = cell.get("row", 0)
                    c = cell.get("col", 0)
                    if 0 <= r < n_rows and 0 <= c < n_cols:
                        grid[r][c] = cell.get("text", "")
                limit = min(args.head_rows, n_rows)
                for ridx in range(limit):
                    record = {
                        "doc_id": doc_id,
                        "table_id": table_id,
                        "page_no": page_no,
                        "row_idx": ridx,
                    }
                    for cidx in range(n_cols):
                        record[f"c{cidx}"] = grid[ridx][cidx]
                    rows.append(record)

    if not rows:
        print("No tables to preview.")
        return

    fieldnames = list(rows[0].keys())
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    main()
