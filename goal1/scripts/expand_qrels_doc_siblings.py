"""Expand document-level qrels to include sibling docs of the same product."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

INTERIM = Path("data/interim")
QUERY_INPUT = (
    Path("testsuite/queries.patched.jsonl")
    if Path("testsuite/queries.patched.jsonl").exists()
    else Path("testsuite/queries.jsonl")
)
OUTPUT_PATH = Path("testsuite/qrels_doc_multi.tsv")


def main() -> None:
    doc_dirs = [d for d in INTERIM.iterdir() if d.is_dir()]
    all_docs = {d.name for d in doc_dirs}
    base_to_docs: dict[str, list[str]] = defaultdict(list)
    for doc_id in all_docs:
        base = doc_id.split("__")[0]
        base_to_docs[base].append(doc_id)

    rows: list[tuple[str, str, int]] = []
    with QUERY_INPUT.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            qid = record["qid"]
            doc_id = record["doc_id"]
            base = doc_id.split("__")[0]
            for sibling in sorted(base_to_docs.get(base, [])):
                rows.append((qid, sibling, 1))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as writer:
        for qid, doc, rel in rows:
            writer.write(f"{qid}\t{doc}\t{rel}\n")

    total_queries = sum(1 for _ in QUERY_INPUT.open("r", encoding="utf-8"))
    avg_positive = len(rows) / max(total_queries, 1)
    print(
        json.dumps(
            {
                "qrels_doc_multi": OUTPUT_PATH.as_posix(),
                "avg_positives_per_qid": avg_positive,
                "queries": total_queries,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
