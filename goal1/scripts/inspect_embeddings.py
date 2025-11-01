"""Inspect embedding parquet caches for basic sanity checks."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ALIASES = [
    "bge_large_zh_v1_5_mean_cos",
    "m3e_large_mean_cos",
    "gte_qwen15_7b_mean_cos",
    "te3_large_cos",
]


def summarize(alias: str) -> dict:
    base = Path("indexes") / alias
    result = {"alias": alias, "ok": True, "notes": []}
    for split in ("corpus", "queries"):
        parquet_path = base / f"{split}.parquet"
        if not parquet_path.exists():
            result["ok"] = False
            result["notes"].append(f"missing {parquet_path}")
            continue
        df = pd.read_parquet(parquet_path)
        rows = len(df)
        dim = len(df["vector"].iloc[0]) if rows else 0
        sample_size = min(100, rows)
        if sample_size > 0:
            sample = np.vstack(df["vector"].iloc[:sample_size].to_numpy())
            norms = np.linalg.norm(sample, axis=1)
            norm_mean = float(np.mean(norms))
        else:
            norm_mean = 0.0
        result[split] = {"rows": rows, "dim": dim, "norm_mean": norm_mean}
    return result


def main() -> None:
    reports = []
    for alias in ALIASES:
        base = Path("indexes") / alias
        if not base.exists():
            continue
        reports.append(summarize(alias))
    print(json.dumps(reports, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

