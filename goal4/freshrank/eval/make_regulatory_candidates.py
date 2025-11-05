"""Construct regulatory candidate sets covering new/old versions."""
from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import dateparser


def load_jsonl(path: Path) -> List[dict]:
    rows: List[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_tags(path: Path) -> Dict[str, dict]:
    mapping: Dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            mapping[payload["doc_id"]] = payload
    return mapping


def load_metadata(path: Path) -> Dict[str, dict]:
    mapping: Dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            mapping[payload["doc_id"]] = payload
    return mapping


def normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    parsed = dateparser.parse(value)
    return parsed.isoformat() if parsed else value


def build_candidates(queries, tags_map, meta_map, per_query: int) -> List[dict]:
    doc_ids = list(tags_map.keys())
    rng = random.Random(42)
    results = []
    for query in queries:
        focus = set(query.get("focus_tags", []))
        positives = [doc_id for doc_id, payload in tags_map.items() if focus & set(payload.get("tags", []))]
        negatives = [doc_id for doc_id in doc_ids if doc_id not in positives]
        rng.shuffle(positives)
        rng.shuffle(negatives)
        selected: List[dict] = []
        pos_count = 1
        for doc_id in positives[:pos_count]:
            base = max(0.05, 0.5 + rng.uniform(-0.05, 0.02))
            selected.append(build_entry(doc_id, tags_map, meta_map, 1.0, base))
        needed = per_query - len(selected)
        for doc_id in negatives[:needed]:
            base = max(0.05, 0.7 + rng.uniform(-0.05, 0.1))
            selected.append(build_entry(doc_id, tags_map, meta_map, 0.0, base))
        results.append({
            "query_id": query["query_id"],
            "query": query["query"],
            "focus_tags": query.get("focus_tags", []),
            "candidates": selected,
        })
    return results


def build_entry(doc_id: str, tags_map: Dict[str, dict], meta_map: Dict[str, dict], label: float, base_score: float) -> dict:
    tag_payload = tags_map.get(doc_id, {})
    meta = meta_map.get(doc_id, {})
    effective_date = meta.get("effective_from")
    if effective_date:
        effective_date = normalize_date(effective_date)
    expired = meta.get("expired")
    if expired is None and meta.get("effective_to"):
        expiry = dateparser.parse(meta["effective_to"])
        if expiry:
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            expired = expiry < datetime.now(timezone.utc)
    return {
        "doc_id": doc_id,
        "chunk_id": None,
        "relevance": round(base_score, 3),
        "label": label,
        "effective_date": effective_date,
        "expired": bool(expired),
        "doc_type": meta.get("doc_type"),
        "tags": tag_payload.get("tags", []),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build regulatory candidates")
    parser.add_argument("--queries", default="eval/queries_regulatory.jsonl")
    parser.add_argument("--tags", default="data/metadata/esg_tags.jsonl")
    parser.add_argument("--metadata", default="data/metadata/metadata.jsonl")
    parser.add_argument("--per-query", type=int, default=24)
    parser.add_argument("--out", default="eval/topk_candidates_regulatory.jsonl")
    args = parser.parse_args()

    queries = load_jsonl(Path(args.queries))
    tags_map = load_tags(Path(args.tags))
    meta_map = load_metadata(Path(args.metadata))
    bundles = build_candidates(queries, tags_map, meta_map, args.per_query)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for row in bundles:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Saved {len(bundles)} queries to {args.out}")


if __name__ == "__main__":
    main()
