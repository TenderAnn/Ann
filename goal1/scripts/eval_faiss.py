"""Evaluate FAISS retrieval metrics for a given embedding alias."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import faiss  # type: ignore
import numpy as np
import pandas as pd


def load_parquet(alias: str, split: str) -> tuple[pd.DataFrame, np.ndarray]:
    path = Path("indexes") / alias / f"{split}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"missing {path}")
    df = pd.read_parquet(path)
    vectors = np.vstack(df["vector"].to_numpy()).astype("float32")
    return df, vectors


def l2norm(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12
    return mat / norms


def build_faiss_index(vectors: np.ndarray, metric: str = "cosine") -> faiss.Index:
    dim = vectors.shape[1]
    if metric == "cosine":
        index = faiss.IndexFlatIP(dim)
    elif metric == "l2":
        index = faiss.IndexFlatL2(dim)
    else:
        raise ValueError(f"unknown metric {metric}")
    index.add(vectors)
    return index


def topk_unique_docs(
    top_indices: np.ndarray,
    corpus_ids: np.ndarray,
    chunk_to_doc: dict[str, str],
    kdoc: int,
) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for ridx in top_indices:
        chunk_id = corpus_ids[ridx]
        doc_id = chunk_to_doc.get(chunk_id)
        if doc_id is None or doc_id in seen:
            continue
        seen.add(doc_id)
        output.append(doc_id)
        if len(output) >= kdoc:
            break
    return output


def recall_at_k(gold: set, preds: list[str], k: int) -> float:
    candidates = preds[:k]
    return 1.0 if any(item in gold for item in candidates) else 0.0


def mrr_at_k(gold: set, preds: list[str], k: int) -> float:
    for rank, candidate in enumerate(preds[:k], start=1):
        if candidate in gold:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(gold: set, preds: list[str], k: int) -> float:
    for rank, candidate in enumerate(preds[:k], start=1):
        if candidate in gold:
            return 1.0 / math.log2(rank + 1)
    return 0.0


def load_qrels(path: Path) -> dict[str, set]:
    qrels: dict[str, set] = defaultdict(set)
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            qid, vid, rel = line.rstrip("\n").split("\t")
            if int(rel) > 0:
                qrels[qid].add(vid)
    return qrels


def evaluate(
    alias: str,
    topk: int = 100,
    metric: str = "cosine",
    longdoc_ids_path: str = "testsuite/longdoc_ids.txt",
    qrels_pass_path: str = "testsuite/qrels_passage.tsv",
    qrels_doc_path: str = "testsuite/qrels_doc.tsv",
) -> dict:
    out_dir = Path("results/faiss") / alias
    out_dir.mkdir(parents=True, exist_ok=True)

    corpus_df, corpus_vecs = load_parquet(alias, "corpus")
    query_df, query_vecs = load_parquet(alias, "queries")

    def norm_mean(vecs: np.ndarray) -> float:
        sample = vecs[: min(1000, len(vecs))]
        return float(np.mean(np.linalg.norm(sample, axis=1)))

    nm_corpus = norm_mean(corpus_vecs)
    nm_queries = norm_mean(query_vecs)
    normalized = 0.98 <= nm_corpus <= 1.02 and 0.98 <= nm_queries <= 1.02

    if metric == "cosine" and not normalized:
        corpus_vecs = l2norm(corpus_vecs)
        query_vecs = l2norm(query_vecs)

    index = build_faiss_index(corpus_vecs, metric=metric)
    distances, indices = index.search(query_vecs, topk)

    corpus_ids = corpus_df["id"].astype(str).to_numpy()
    corpus_docs = corpus_df["doc_id"].astype(str).to_numpy()
    chunk_to_doc = {cid: did for cid, did in zip(corpus_ids, corpus_docs)}

    qids = query_df["id"].astype(str).to_numpy()
    majors = (
        query_df["major"].fillna("unknown").astype(str).to_numpy()
        if "major" in query_df.columns
        else np.array(["unknown"] * len(query_df))
    )
    topics = (
        query_df["topic"].fillna("unknown").astype(str).to_numpy()
        if "topic" in query_df.columns
        else np.array(["unknown"] * len(query_df))
    )

    qrels_passage = load_qrels(Path(qrels_pass_path))
    qrels_doc = load_qrels(Path(qrels_doc_path))

    longdoc_set: set[str] = set()
    longdoc_path = Path(longdoc_ids_path)
    if longdoc_path.exists():
        longdoc_set = set(filter(None, longdoc_path.read_text(encoding="utf-8").splitlines()))

    def init_metrics() -> dict[str, list[float]]:
        return {"R@5": [], "R@10": [], "R@20": [], "MRR@10": [], "nDCG@10": []}

    passage_all = init_metrics()
    doc_all = init_metrics()
    passage_by_major: dict[str, dict[str, list[float]]] = defaultdict(init_metrics)
    doc_by_major: dict[str, dict[str, list[float]]] = defaultdict(init_metrics)
    passage_longdoc = init_metrics()
    doc_longdoc = init_metrics()

    topk_dir = out_dir / "topk"
    topk_dir.mkdir(parents=True, exist_ok=True)

    for qidx in range(len(qids)):
        qid = qids[qidx]
        major = majors[qidx]
        top_indices = indices[qidx].tolist()
        top_chunks = [corpus_ids[i] for i in top_indices]
        top_docs = topk_unique_docs(indices[qidx], corpus_ids, chunk_to_doc, kdoc=topk)

        gold_pass = qrels_passage.get(qid, set())
        gold_doc = qrels_doc.get(qid, set())

        def update_bucket(bucket: dict[str, list[float]], predictions: list[str]) -> None:
            bucket["R@5"].append(recall_at_k(gold_pass, predictions, 5))
            bucket["R@10"].append(recall_at_k(gold_pass, predictions, 10))
            bucket["R@20"].append(recall_at_k(gold_pass, predictions, 20))
            bucket["MRR@10"].append(mrr_at_k(gold_pass, predictions, 10))
            bucket["nDCG@10"].append(ndcg_at_k(gold_pass, predictions, 10))

        def update_doc_bucket(bucket: dict[str, list[float]], predictions: list[str]) -> None:
            bucket["R@5"].append(recall_at_k(gold_doc, predictions, 5))
            bucket["R@10"].append(recall_at_k(gold_doc, predictions, 10))
            bucket["R@20"].append(recall_at_k(gold_doc, predictions, 20))
            bucket["MRR@10"].append(mrr_at_k(gold_doc, predictions, 10))
            bucket["nDCG@10"].append(ndcg_at_k(gold_doc, predictions, 10))

        update_bucket(passage_all, top_chunks)
        update_bucket(passage_by_major[major], top_chunks)
        update_doc_bucket(doc_all, top_docs)
        update_doc_bucket(doc_by_major[major], top_docs)

        if any(doc in longdoc_set for doc in gold_doc):
            update_bucket(passage_longdoc, top_chunks)
            update_doc_bucket(doc_longdoc, top_docs)

        sample_k = min(20, len(top_chunks))
        payload = {
            "qid": qid,
            "major": major,
            "topic": topics[qidx],
            "top_chunks": [
                {
                    "chunk_id": top_chunks[i],
                    "score": float(distances[qidx][i]),
                    "doc_id": chunk_to_doc.get(top_chunks[i]),
                }
                for i in range(sample_k)
            ],
            "gold_passage": list(gold_pass),
            "gold_doc": list(gold_doc),
        }
        (topk_dir / f"{qid}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def average(metric_bucket: dict[str, list[float]]) -> dict[str, float]:
        return {key: round(float(np.mean(values)), 4) if values else 0.0 for key, values in metric_bucket.items()}

    metrics = {
        "alias": alias,
        "corpus_rows": int(len(corpus_df)),
        "query_rows": int(len(query_df)),
        "dim": int(len(corpus_df["vector"].iloc[0])) if len(corpus_df) else 0,
        "norm_mean": {"corpus": round(nm_corpus, 4), "queries": round(nm_queries, 4)},
        "passage": {
            "all": average(passage_all),
            "by_major": {key: average(bucket) for key, bucket in passage_by_major.items()},
            "longdoc": average(passage_longdoc),
        },
        "doc": {
            "all": average(doc_all),
            "by_major": {key: average(bucket) for key, bucket in doc_by_major.items()},
            "longdoc": average(doc_longdoc),
        },
        "params": {"topk": topk, "metric": metric, "normalized": normalized},
    }

    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metrics["doc"]["all"], ensure_ascii=False, indent=2))
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alias", required=True)
    parser.add_argument("--topk", type=int, default=100)
    parser.add_argument("--metric", default="cosine", choices=["cosine", "l2"])
    parser.add_argument("--longdoc-ids", default="testsuite/longdoc_ids.txt")
    parser.add_argument("--qrels-pass", default="testsuite/qrels_passage.tsv")
    parser.add_argument("--qrels-doc", default="testsuite/qrels_doc.tsv")
    args = parser.parse_args()
    evaluate(
        args.alias,
        topk=args.topk,
        metric=args.metric,
        longdoc_ids_path=args.longdoc_ids,
        qrels_pass_path=args.qrels_pass,
        qrels_doc_path=args.qrels_doc,
    )


if __name__ == "__main__":
    main()
