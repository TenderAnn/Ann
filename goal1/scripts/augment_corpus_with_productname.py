"""Augment chunk texts with product name, doc type, and doc id prefix."""

from __future__ import annotations

import json
from pathlib import Path

ARTIFACT_DIR = Path("artifacts")
INPUT_PATH = Path("corpus/chunks/all_chunks.jsonl")
OUTPUT_PATH = Path("corpus/chunks/all_chunks.with_name.jsonl")


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def main() -> None:
    product_map = json.loads((ARTIFACT_DIR / "product_name_map.json").read_text(encoding="utf-8"))
    label_map = json.loads((ARTIFACT_DIR / "doc_label_map.json").read_text(encoding="utf-8"))

    records = load_jsonl(INPUT_PATH)
    with OUTPUT_PATH.open("w", encoding="utf-8") as writer:
        for record in records:
            doc_id = record.get("doc_id")
            base_id = doc_id.split("__")[0] if doc_id else ""
            name = product_map.get(doc_id, base_id)
            label = label_map.get(doc_id, "")
            prefix_parts = [f"DocID:{base_id}"]
            if name:
                prefix_parts.append(f"Product:{name}")
            if label:
                prefix_parts.append(f"Type:{label}")
            prefix = " | ".join(prefix_parts)
            text = record.get("text", "")
            augmented = f"{prefix}\n{text}"
            record["text"] = augmented
            writer.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(json.dumps({"written": len(records), "output": str(OUTPUT_PATH)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
