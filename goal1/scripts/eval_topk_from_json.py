"""Evaluate metrics from generic top-k JSON outputs."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Set

import numpy as np


def read_jsonl(path: Path) -> Iterable[Dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_qrels(path: Path) -> Dict[str, Set[str]]:
    qrels: Dict[str, Set[str]] = defaultdict(set)
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            qid, vid, rel = line.rstrip("\n").split("\t")
            if int(rel) > 0:
                qrels[qid].add(vid)
    return qrels


def load_chunk_doc_map(corpus_path: Path) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    with corpus_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            mapping[record["chunk_id"]] = record["doc_id"]
    return mapping


def recall_at_k(gold: Set[str], preds: List[str], k: int) -> float:
    return 1.0 if any(item in gold for item in preds[:k]) else 0.0


def mrr_at_k(gold: Set[str], preds: List[str], k: int) -> float:
    for rank, item in enumerate(preds[:k], start=1):
        if item in gold:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(gold: Set[str], preds: List[str], k: int) -> float:
    for rank, item in enumerate(preds[:k], start=1):
        if item in gold:
            return 1.0 / np.log2(rank + 1)
    return 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topk-dir", required=True)
    parser.add_argument("--queries", default="testsuite/queries.patched3.jsonl")
    parser.add_argument("--corpus", default="corpus/chunks/all_chunks.with_name.jsonl")
    parser.add_argument("--qrels-pass", default="testsuite/qrels_passage.tsv")
    parser.add_argument("--qrels-doc", default="testsuite/qrels_doc_multi.tsv")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    topk_dir = Path(args.topk_dir)
    files = sorted(topk_dir.glob("Q*.json"))

    chunk_to_doc = load_chunk_doc_map(Path(args.corpus))
    qrels_pass = load_qrels(Path(args.qrels_pass))
    qrels_doc = load_qrels(Path(args.qrels_doc))

    passage_r10: List[float] = []
    passage_mrr10: List[float] = []
    passage_ndcg10: List[float] = []
    doc_r5: List[float] = []
    doc_r10: List[float] = []
    doc_r20: List[float] = []
    doc_mrr10: List[float] = []
    doc_ndcg10: List[float] = []

    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        qid = data.get("qid")
        chunks = [entry["chunk_id"] for entry in data.get("top_chunks", [])]
        docs = []
        seen_docs = set()
        for cid in chunks:
            doc_id = chunk_to_doc.get(cid)
            if doc_id and doc_id not in seen_docs:
                docs.append(doc_id)
                seen_docs.add(doc_id)

        gold_pass = qrels_pass.get(qid, set())
        gold_doc = qrels_doc.get(qid, set())

        passage_r10.append(recall_at_k(gold_pass, chunks, 10))
        passage_mrr10.append(mrr_at_k(gold_pass, chunks, 10))
        passage_ndcg10.append(ndcg_at_k(gold_pass, chunks, 10))

        doc_r5.append(recall_at_k(gold_doc, docs, 5))
        doc_r10.append(recall_at_k(gold_doc, docs, 10))
        doc_r20.append(recall_at_k(gold_doc, docs, 20))
        doc_mrr10.append(mrr_at_k(gold_doc, docs, 10))
        doc_ndcg10.append(ndcg_at_k(gold_doc, docs, 10))

    result = {
        "pass": {
            "R@10": round(float(np.mean(passage_r10)), 4),
            "MRR@10": round(float(np.mean(passage_mrr10)), 4),
            "nDCG@10": round(float(np.mean(passage_ndcg10)), 4),
        },
        "doc": {
            "R@5": round(float(np.mean(doc_r5)), 4),
            "R@10": round(float(np.mean(doc_r10)), 4),
            "R@20": round(float(np.mean(doc_r20)), 4),
            "MRR@10": round(float(np.mean(doc_mrr10)), 4),
            "nDCG@10": round(float(np.mean(doc_ndcg10)), 4),
        },
    }

    out_path = Path(args.out) if args.out else topk_dir.parent / "metrics.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
