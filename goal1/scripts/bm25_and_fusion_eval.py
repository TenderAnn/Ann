"""Hybrid BM25 + vector (RRF) evaluation pipeline."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import jieba  # type: ignore
import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi  # type: ignore


def load_jsonl(path: Path) -> List[Dict]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def tokenise(text: str) -> List[str]:
    return [tok.strip() for tok in jieba.lcut(text, cut_all=False) if tok.strip()]


def recall_at_k(gold: set, preds: List[str], k: int) -> float:
    return 1.0 if any(p in gold for p in preds[:k]) else 0.0


def mrr_at_k(gold: set, preds: List[str], k: int) -> float:
    for rank, item in enumerate(preds[:k], start=1):
        if item in gold:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(gold: set, preds: List[str], k: int) -> float:
    for rank, item in enumerate(preds[:k], start=1):
        if item in gold:
            return 1.0 / math.log2(rank + 1)
    return 0.0


def load_qrels(path: Path) -> Dict[str, set]:
    qrels: Dict[str, set] = defaultdict(set)
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            qid, vid, rel = line.rstrip("\n").split("\t")
            if int(rel) > 0:
                qrels[qid].add(vid)
    return qrels


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def rrf_fuse(
    bm25_scores: List[Tuple[str, int]],
    faiss_scores: List[Tuple[str, int]],
    k: int = 60,
    topk: int = 100,
) -> List[str]:
    score_map: Dict[str, float] = defaultdict(float)
    for rank, chunk_id in enumerate([cid for cid, _ in bm25_scores]):
        score_map[chunk_id] += 1.0 / (k + rank + 1)
    for rank, chunk_id in enumerate([cid for cid, _ in faiss_scores]):
        score_map[chunk_id] += 1.0 / (k + rank + 1)
    sorted_items = sorted(score_map.items(), key=lambda item: item[1], reverse=True)
    return [cid for cid, _ in sorted_items[:topk]]


def evaluate(
    alias: str,
    corpus_path: Path,
    queries_path: Path,
    qrels_pass_path: Path,
    qrels_doc_path: Path,
    faiss_dir: Path,
    out_dir: Path,
    topk: int = 100,
    bm25_topn: int = 200,
    rrf_k: int = 60,
) -> Dict:
    ensure_dir(out_dir)
    ensure_dir(out_dir / "topk")

    corpus_records = load_jsonl(corpus_path)
    queries = load_jsonl(queries_path)

    chunk_texts = [record["text"] for record in corpus_records]
    chunk_ids = [record["chunk_id"] for record in corpus_records]
    chunk_doc_ids = [record.get("doc_id") for record in corpus_records]
    chunk_tokens = [tokenise(text) for text in chunk_texts]
    bm25 = BM25Okapi(chunk_tokens)

    chunk_index = {cid: idx for idx, cid in enumerate(chunk_ids)}

    qrels_passage = load_qrels(qrels_pass_path)
    qrels_doc = load_qrels(qrels_doc_path)

    passage_metrics = {"R@5": [], "R@10": [], "R@20": [], "MRR@10": [], "nDCG@10": []}
    doc_metrics = {"R@5": [], "R@10": [], "R@20": [], "MRR@10": [], "nDCG@10": []}
    doc_long_metrics = {"R@5": [], "R@10": [], "R@20": [], "MRR@10": [], "nDCG@10": []}

    longdoc_ids = set(Path("testsuite/longdoc_ids.txt").read_text(encoding="utf-8").splitlines()) if Path("testsuite/longdoc_ids.txt").exists() else set()

    for query in queries:
        qid = query["qid"]
        tokens = tokenise(query["query"])
        scores = bm25.get_scores(tokens)
        top_indices = np.argsort(scores)[::-1][:bm25_topn]
        bm25_ranked = [(chunk_ids[idx], rank) for rank, idx in enumerate(top_indices)]

        faiss_path = faiss_dir / f"{qid}.json"
        with faiss_path.open("r", encoding="utf-8") as f:
            faiss_payload = json.load(f)
        faiss_ranked = [(entry["chunk_id"], idx) for idx, entry in enumerate(faiss_payload["top_chunks"])]

        fused_chunk_ids = rrf_fuse(bm25_ranked, faiss_ranked, k=rrf_k, topk=topk)

        top_chunks_payload = []
        for cid in fused_chunk_ids[:topk]:
            idx = chunk_index[cid]
            doc_id = chunk_doc_ids[idx]
            bm25_rank = next((rank for chunk, rank in bm25_ranked if chunk == cid), None)
            faiss_rank = next((rank for chunk, rank in faiss_ranked if chunk == cid), None)
            top_chunks_payload.append(
                {
                    "chunk_id": cid,
                    "doc_id": doc_id,
                    "bm25_rank": bm25_rank,
                    "faiss_rank": faiss_rank,
                }
            )

        with (out_dir / "topk" / f"{qid}.json").open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "qid": qid,
                    "query": query["query"],
                    "top_chunks": top_chunks_payload,
                    "gold_passage": list(qrels_passage.get(qid, set())),
                    "gold_doc": list(qrels_doc.get(qid, set())),
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )

        gold_pass = qrels_passage.get(qid, set())
        passage_metrics["R@5"].append(recall_at_k(gold_pass, fused_chunk_ids, 5))
        passage_metrics["R@10"].append(recall_at_k(gold_pass, fused_chunk_ids, 10))
        passage_metrics["R@20"].append(recall_at_k(gold_pass, fused_chunk_ids, 20))
        passage_metrics["MRR@10"].append(mrr_at_k(gold_pass, fused_chunk_ids, 10))
        passage_metrics["nDCG@10"].append(ndcg_at_k(gold_pass, fused_chunk_ids, 10))

        doc_seen = []
        seen_docs = set()
        for cid in fused_chunk_ids:
            doc_id = chunk_doc_ids[chunk_index[cid]]
            if doc_id not in seen_docs:
                doc_seen.append(doc_id)
                seen_docs.add(doc_id)

        gold_docs = qrels_doc.get(qid, set())
        doc_metrics["R@5"].append(recall_at_k(gold_docs, doc_seen, 5))
        doc_metrics["R@10"].append(recall_at_k(gold_docs, doc_seen, 10))
        doc_metrics["R@20"].append(recall_at_k(gold_docs, doc_seen, 20))
        doc_metrics["MRR@10"].append(mrr_at_k(gold_docs, doc_seen, 10))
        doc_metrics["nDCG@10"].append(ndcg_at_k(gold_docs, doc_seen, 10))

        if any(doc in longdoc_ids for doc in gold_docs):
            doc_long_metrics["R@5"].append(recall_at_k(gold_docs, doc_seen, 5))
            doc_long_metrics["R@10"].append(recall_at_k(gold_docs, doc_seen, 10))
            doc_long_metrics["R@20"].append(recall_at_k(gold_docs, doc_seen, 20))
            doc_long_metrics["MRR@10"].append(mrr_at_k(gold_docs, doc_seen, 10))
            doc_long_metrics["nDCG@10"].append(ndcg_at_k(gold_docs, doc_seen, 10))

    def summarise(metrics: Dict[str, List[float]]) -> Dict[str, float]:
        return {key: round(float(np.mean(values)), 4) if values else 0.0 for key, values in metrics.items()}

    summary = {
        "alias": alias,
        "topk": topk,
        "bm25_topn": bm25_topn,
        "rrf_k": rrf_k,
        "passage": {"all": summarise(passage_metrics)},
        "doc": {"all": summarise(doc_metrics), "longdoc": summarise(doc_long_metrics)},
    }

    with (out_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alias", required=True)
    parser.add_argument("--corpus", default="corpus/chunks/all_chunks.with_name.jsonl")
    parser.add_argument("--queries", default=None)
    parser.add_argument("--qrels-pass", default="testsuite/qrels_passage.tsv")
    parser.add_argument(
        "--qrels-doc",
        default="testsuite/qrels_doc_multi.tsv" if Path("testsuite/qrels_doc_multi.tsv").exists() else "testsuite/qrels_doc.tsv",
    )
    parser.add_argument("--topk", type=int, default=100)
    parser.add_argument("--bm25-topn", type=int, default=200)
    parser.add_argument("--rrf-k", type=int, default=60)
    args = parser.parse_args()

    queries_path = (
        Path(args.queries)
        if args.queries
        else (
            Path("testsuite/queries.patched3.jsonl")
            if Path("testsuite/queries.patched3.jsonl").exists()
            else (
                Path("testsuite/queries.patched.jsonl")
                if Path("testsuite/queries.patched.jsonl").exists()
                else Path("testsuite/queries.jsonl")
            )
        )
    )

    faiss_dir = Path("results/faiss") / args.alias / "topk"
    hybrid_dir = ensure_dir(Path("results/hybrid") / args.alias)

    summary = evaluate(
        alias=args.alias,
        corpus_path=Path(args.corpus),
        queries_path=queries_path,
        qrels_pass_path=Path(args.qrels_pass),
        qrels_doc_path=Path(args.qrels_doc),
        faiss_dir=faiss_dir,
        out_dir=hybrid_dir,
        topk=args.topk,
        bm25_topn=args.bm25_topn,
        rrf_k=args.rrf_k,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
