"""Rewrite testsuite queries with resolved product names."""

from __future__ import annotations

import json
import re
from pathlib import Path


QUERY_INPUT = Path("testsuite/queries.jsonl")
QUERY_OUTPUT = Path("testsuite/queries.patched.jsonl")
PRODUCT_MAP_PATH = Path("artifacts/product_name_map.json")
LABEL_MAP_PATH = Path("artifacts/doc_label_map.json")


def main() -> None:
    product_map = json.loads(PRODUCT_MAP_PATH.read_text(encoding="utf-8"))
    label_map = json.loads(LABEL_MAP_PATH.read_text(encoding="utf-8"))

    patched = []
    changed = 0
    with QUERY_INPUT.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            doc_id = record.get("doc_id", "")
            original_prod = record.get("prod", "")
            resolved_name = product_map.get(doc_id, original_prod)
            label = label_map.get(doc_id, "")
            display = f"《{resolved_name}》{label}" if label and label != "文档" else f"《{resolved_name}》"

            query_text = record["query"]
            if original_prod and original_prod in query_text:
                patched_query = query_text.replace(original_prod, display, 1)
            else:
                match = re.match(r"^(.{1,20}?)(的|\s)", query_text)
                if match:
                    patched_query = display + query_text[match.end() :]
                else:
                    patched_query = f"{display} {query_text}"

            if patched_query != query_text:
                changed += 1

            record["query"] = patched_query
            record["prod"] = resolved_name
            patched.append(record)

    QUERY_OUTPUT.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in patched),
        encoding="utf-8",
    )
    print(json.dumps({"patched": changed, "total": len(patched)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

