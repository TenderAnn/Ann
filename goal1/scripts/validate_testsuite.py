"""Validate generated testsuite for basic consistency."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def read_jsonl(path: Path) -> Iterable[Dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def read_qrels(path: Path) -> Dict[str, List[Tuple[str, int]]]:
    results: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            qid, vid, rel = line.rstrip("\n").split("\t")
            results[qid].append((vid, int(rel)))
    return results


def main() -> None:
    root = Path("testsuite")
    queries = list(read_jsonl(root / "queries.jsonl"))
    qrels_passage = read_qrels(root / "qrels_passage.tsv")
    qrels_doc = read_qrels(root / "qrels_doc.tsv")

    qids = {query["qid"] for query in queries}
    missing_passage = [qid for qid in qids if qid not in qrels_passage]
    missing_doc = [qid for qid in qids if qid not in qrels_doc]
    duplicate_qids = len(queries) != len(qids)

    major_counts: Dict[str, int] = defaultdict(int)
    topic_counts: Dict[str, int] = defaultdict(int)
    doc_counts: Dict[str, int] = defaultdict(int)
    for query in queries:
        major_counts[query["major"]] += 1
        topic_counts[query["topic"]] += 1
        doc_counts[query["doc_id"]] += 1

    report = {
        "total_queries": len(queries),
        "majors": dict(major_counts),
        "topics": dict(topic_counts),
        "unique_docs": len(doc_counts),
        "missing_in_passage_qrels": len(missing_passage),
        "missing_in_doc_qrels": len(missing_doc),
        "has_duplicate_qids": duplicate_qids,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if missing_passage or missing_doc or duplicate_qids:
        sys.exit(1)


if __name__ == "__main__":
    main()

