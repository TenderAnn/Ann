"""Compute ingestion SLO percentiles from event logs."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import List


def parse_time(value: str) -> datetime:
    value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = (len(values) - 1) * pct
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return values[f]
    return values[f] + (values[c] - values[f]) * (k - f)


def run(args: argparse.Namespace) -> None:
    events = []
    with Path(args.input).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            events.append(json.loads(line))
    latencies = []
    metadata_latencies = []
    for event in events:
        ingested = parse_time(event["ingested_at"])
        served = parse_time(event["served_at"])
        metadata_ready = parse_time(event["metadata_ready_at"])
        total_minutes = (served - ingested).total_seconds() / 60
        meta_minutes = (metadata_ready - ingested).total_seconds() / 60
        latencies.append(total_minutes)
        metadata_latencies.append(meta_minutes)
    report = {
        "total_minutes": {
            "p50": round(percentile(latencies, 0.5), 2),
            "p90": round(percentile(latencies, 0.9), 2),
            "p99": round(percentile(latencies, 0.99), 2),
        },
        "metadata_minutes": {
            "p50": round(percentile(metadata_latencies, 0.5), 2),
            "p90": round(percentile(metadata_latencies, 0.9), 2),
            "p99": round(percentile(metadata_latencies, 0.99), 2),
        },
        "records": len(events),
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Ingestion SLO report saved to {args.out}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute ingestion SLO percentiles")
    parser.add_argument("--input", default="data/metadata/ingestion_events.jsonl")
    parser.add_argument("--out", default="eval/reports/ingestion_slo.json")
    return parser.parse_args()


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
