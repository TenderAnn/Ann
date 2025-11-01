"""Rewrite queries with cleaned product name and base id anchors."""

from __future__ import annotations

import json
import re
from pathlib import Path

QUERY_INPUT = (
    Path("testsuite/queries.patched3.jsonl")
    if Path("testsuite/queries.patched3.jsonl").exists()
    else (
        Path("testsuite/queries.patched.jsonl")
        if Path("testsuite/queries.patched.jsonl").exists()
        else Path("testsuite/queries.jsonl")
    )
)
QUERY_OUTPUT = Path("testsuite/queries.patched3.jsonl")
PRODUCT_MAP = Path("artifacts/product_name_map.clean.json")
LABEL_MAP = Path("artifacts/doc_label_map.json")


def main() -> None:
    product_map = json.loads(PRODUCT_MAP.read_text(encoding="utf-8"))
    label_map = json.loads(LABEL_MAP.read_text(encoding="utf-8"))
    rewritten = []
    changed = 0

    with QUERY_INPUT.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            doc_id = record["doc_id"]
            base = doc_id.split("__")[0]
            clean_name = product_map.get(doc_id) or base
            label = label_map.get(doc_id, "")
            display = f"《{clean_name}》"
            if label and label != "文档":
                display += f"（{label}）"
            display += f"（编号 {base}）"

            query_text = record["query"]
            if "《" in query_text and "》" in query_text:
                patched = re.sub(r"《.*?》", display, query_text, count=1)
            else:
                patched = f"{display} {query_text}"

            if patched != query_text:
                changed += 1

            record["query"] = patched
            record["prod"] = clean_name
            rewritten.append(record)

    QUERY_OUTPUT.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in rewritten),
        encoding="utf-8",
    )
    print(json.dumps({"patched": changed, "total": len(rewritten)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
