"""Cross-Encoder reranking over hybrid top-k candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from tqdm import tqdm


def load_chunks_map(corpus_jsonl: str) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    with open(corpus_jsonl, "r", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            mapping[record["chunk_id"]] = record["text"]
    return mapping


def read_jsonl(path: Path) -> List[Dict]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alias", required=True, help="Alias name for output directory naming")
    parser.add_argument("--topk-dir", required=True, help="Input top-k directory (e.g., hybrid topk)")
    parser.add_argument("--out-dir", default=None, help="Output root directory (default results/rerank/<alias>/)")
    parser.add_argument("--queries", default="testsuite/queries.patched3.jsonl")
    parser.add_argument("--corpus", default="corpus/chunks/all_chunks.with_name.jsonl")
    parser.add_argument("--model", default="BAAI/bge-reranker-large")
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=512)
    args = parser.parse_args()

    if torch.cuda.is_available():
        device = "cuda"
    elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSequenceClassification.from_pretrained(args.model)
    model.to(device).eval()

    query_map = {item["qid"]: item["query"] for item in read_jsonl(Path(args.queries))}
    chunk_map = load_chunks_map(args.corpus)

    in_dir = Path(args.topk_dir)
    out_root = Path(args.out_dir) if args.out_dir else Path("results") / "rerank" / args.alias
    out_root.mkdir(parents=True, exist_ok=True)
    out_dir = out_root / "topk"
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(in_dir.glob("Q*.json"))
    for fp in tqdm(files, desc="rerank"):
        data = json.loads(fp.read_text(encoding="utf-8"))
        qid = data.get("qid")
        query = query_map.get(qid, "")
        candidates = data.get("top_chunks", [])[:100]
        chunk_texts: List[str] = []
        chunk_ids: List[str] = []
        for entry in candidates:
            cid = entry.get("chunk_id")
            text = chunk_map.get(cid, "")
            if text:
                chunk_texts.append(text)
                chunk_ids.append(cid)

        if not chunk_ids:
            (out_dir / fp.name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            continue

        scores: List[float] = []
        with torch.no_grad():
            for idx in range(0, len(chunk_texts), args.batch):
                batch_texts = chunk_texts[idx : idx + args.batch]
                encoded = tokenizer(
                    [query] * len(batch_texts),
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=args.max_length,
                    return_tensors="pt",
                )
                encoded = {key: value.to(device) for key, value in encoded.items()}
                logits = model(**encoded).logits.squeeze(-1)
                scores.extend(logits.detach().cpu().tolist())

        order = np.argsort(scores)[::-1]
        reranked_chunks = [
            {"chunk_id": chunk_ids[i], "score": float(scores[i])} for i in order
        ]
        payload = {"qid": qid, "top_chunks": reranked_chunks}
        (out_dir / fp.name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Reranked files -> {out_dir}")


if __name__ == "__main__":
    main()
