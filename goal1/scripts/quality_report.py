"""Generate quality metrics and samples for chunked corpus."""

from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", default="corpus/chunks/all_chunks.jsonl", help="Chunks JSONL path")
    parser.add_argument("--out", default="results/chunk_quality.json", help="Quality report output")
    parser.add_argument("--samples", default="results/chunk_samples.jsonl", help="Sample chunks output")
    parser.add_argument("--sample-n", type=int, default=20, help="Number of samples")
    args = parser.parse_args()

    chunks: List[Dict] = []
    page_keys = set()
    cross_page = 0
    section_counts: Counter = Counter()

    with Path(args.chunks).open("r", encoding="utf-8") as fh:
        for line in fh:
            record = json.loads(line)
            chunks.append(record)
            page_span: Tuple[int, int] = tuple(record.get("page_span", [0, 0]))  # type: ignore
            if page_span[0] != page_span[1]:
                cross_page += 1
            for page_no in range(page_span[0], page_span[1] + 1):
                page_keys.add((record["doc_id"], page_no))
            section_path = tuple(record.get("section_path") or [])
            section_counts[section_path] += 1

    lengths = [len(rec.get("text", "")) for rec in chunks]
    avg_len = round(sum(lengths) / max(1, len(lengths)), 2) if lengths else 0.0
    median_len = round(statistics.median(lengths), 2) if lengths else 0.0
    cross_ratio = round(cross_page / max(1, len(chunks)), 4) if chunks else 0.0

    top_sections = [
        {"section_path": list(key), "count": count}
        for key, count in section_counts.most_common(10)
    ]

    quality = {
        "total_chunks": len(chunks),
        "avg_len": avg_len,
        "median_len": median_len,
        "cross_page_ratio": cross_ratio,
        "unique_doc_pages_with_chunks": len(page_keys),
        "top_section_paths": top_sections,
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")

    random.seed(42)
    samples = random.sample(chunks, min(args.sample_n, len(chunks)))
    with Path(args.samples).open("w", encoding="utf-8") as sample_file:
        for sample in samples:
            entry = {
                "chunk_id": sample.get("chunk_id"),
                "doc_id": sample.get("doc_id"),
                "page_span": sample.get("page_span"),
                "section_path": sample.get("section_path"),
                "preview": (sample.get("text") or "")[:240],
            }
            sample_file.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(json.dumps(quality, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

