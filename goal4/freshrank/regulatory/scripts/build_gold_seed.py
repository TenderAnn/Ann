"""Build stratified gold template for regulatory tags."""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TARGET_TAGS = [
    "esg",
    "rating",
    "data_security",
    "consumer_protection",
    "sales_compliance",
    "aml",
    "disclosure_gov",
]


@dataclass
class PredRecord:
    doc_id: str
    chunk_id: Optional[str]
    tags: List[str]
    evidence: List[str]


def load_predictions(path: Path) -> List[PredRecord]:
    records: List[PredRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            records.append(
                PredRecord(
                    doc_id=payload.get("doc_id"),
                    chunk_id=payload.get("chunk_id"),
                    tags=payload.get("tags", []),
                    evidence=payload.get("evidence", []),
                )
            )
    return records


def stratified_sample(records: List[PredRecord], per_class: int, seed: int) -> Dict[str, List[PredRecord]]:
    rng = random.Random(seed)
    buckets: Dict[str, List[PredRecord]] = {tag: [] for tag in TARGET_TAGS}
    for record in records:
        for tag in record.tags:
            if tag in buckets:
                buckets[tag].append(record)
    sampled: Dict[str, List[PredRecord]] = {}
    for tag, items in buckets.items():
        if not items:
            sampled[tag] = []
            continue
        if len(items) <= per_class:
            sampled[tag] = items
        else:
            sampled[tag] = rng.sample(items, per_class)
    return sampled


def discover_negatives(records: List[PredRecord], corpus_dir: Path, neg_count: int, seed: int) -> List[PredRecord]:
    rng = random.Random(seed)
    predicted_ids = {(rec.doc_id, rec.chunk_id) for rec in records}
    candidates: List[PredRecord] = []
    for path in corpus_dir.glob("*.txt"):
        doc_id = path.stem
        if (doc_id, None) in predicted_ids:
            continue
        candidates.append(PredRecord(doc_id=doc_id, chunk_id=None, tags=[], evidence=[]))
    if not candidates:
        return []
    if len(candidates) <= neg_count:
        return candidates
    return rng.sample(candidates, neg_count)


def write_jsonl(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build gold template for regulatory tagging")
    parser.add_argument("--pred", required=True, help="Path to esg_tags predictions")
    parser.add_argument("--corpus", required=True, help="Directory with parsed docs")
    parser.add_argument("--per-class", type=int, default=20)
    parser.add_argument("--neg", type=int, default=20)
    parser.add_argument("--out", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--auto-fill", action="store_true", help="Fill tags with suggestions for synthetic datasets")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pred_path = Path(args.pred)
    corpus_dir = Path(args.corpus)
    records = load_predictions(pred_path)
    sampled = stratified_sample(records, args.per_class, args.seed)
    negatives = discover_negatives(records, corpus_dir, args.neg, args.seed)

    grouped: Dict[Tuple[str, Optional[str]], dict] = {}
    for tag in TARGET_TAGS:
        for record in sampled.get(tag, []):
            key = (record.doc_id, record.chunk_id)
            entry = grouped.setdefault(
                key,
                {
                    "doc_id": record.doc_id,
                    "chunk_id": record.chunk_id,
                    "tags": set(),
                    "rationale": "" if not args.auto_fill else (record.evidence[0] if record.evidence else "synthetic evidence"),
                    "suggested_tags": set(),
                },
            )
            if args.auto_fill:
                entry["tags"].add(tag)
            entry["suggested_tags"].add(tag)
    for record in negatives:
        key = (record.doc_id, record.chunk_id)
        grouped.setdefault(
            key,
            {
                "doc_id": record.doc_id,
                "chunk_id": record.chunk_id,
                "tags": set(),
                "rationale": "",
                "suggested_tags": set(),
            },
        )

    rows = []
    for entry in grouped.values():
        rows.append(
            {
                "doc_id": entry["doc_id"],
                "chunk_id": entry["chunk_id"],
                "tags": sorted(entry["tags"]),
                "rationale": entry["rationale"],
                "suggested_tags": sorted(entry["suggested_tags"]),
            }
        )

    write_jsonl(Path(args.out), rows)
    print(f"Wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
