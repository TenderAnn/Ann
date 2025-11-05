"""Summarize table extraction stats per document."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from kg_fusion.paths import EVAL_ROOT, data_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", default=str(data_path("tables")))
    parser.add_argument("--report", default=str(EVAL_ROOT / "reports" / "table_stats.json"))
    args = parser.parse_args()

    tables_dir = Path(args.tables)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    stats = {"docs": {}, "total_tables": 0, "total_cells": 0}
    for file in sorted(tables_dir.glob("*.tables.jsonl")):
        doc_name = file.stem
        doc_info = {"tables": 0, "cells": 0}
        with file.open(encoding="utf-8") as fh:
            for line in fh:
                table = json.loads(line)
                doc_info["tables"] += 1
                doc_info["cells"] += len(table.get("cells", []))
        stats["docs"][doc_name] = doc_info
        stats["total_tables"] += doc_info["tables"]
        stats["total_cells"] += doc_info["cells"]

    report_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
