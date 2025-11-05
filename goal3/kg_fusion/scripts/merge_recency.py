"""Merge recency metadata (auto + overrides) into nodes.csv."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from kg_fusion.paths import data_path


def main(meta_csv: str, override_csv: str | None, nodes_csv: str, out_csv: str) -> None:
    meta = pd.read_csv(meta_csv)
    if override_csv and Path(override_csv).exists():
        overrides = pd.read_csv(override_csv)
        meta = (
            meta.set_index("doc_id")
            .combine_first(overrides.set_index("doc_id"))
            .reset_index()
        )
    nodes = pd.read_csv(nodes_csv)

    def _apply(row):
        if row["node_type"] != "ProductVersion":
            return row
        props = json.loads(row["props_json"])
        doc_id = props.get("doc_id")
        if not doc_id:
            row["props_json"] = json.dumps(props, ensure_ascii=False)
            return row
        match = meta[meta["doc_id"] == doc_id]
        if match.empty:
            row["props_json"] = json.dumps(props, ensure_ascii=False)
            return row
        eff = str(match.iloc[0].get("effective_date") or "").strip()
        dis = str(match.iloc[0].get("discontinue_date") or "").strip()
        if eff:
            props["effective_date"] = eff
        if dis:
            props["discontinue_date"] = dis
        row["props_json"] = json.dumps(props, ensure_ascii=False)
        return row

    nodes = nodes.apply(_apply, axis=1)
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    nodes.to_csv(out_csv, index=False)
    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--meta", default=str(data_path("kg", "recency_meta.csv")))
    parser.add_argument("--override", default=str(data_path("kg", "recency_override.csv")))
    parser.add_argument("--nodes", default=str(data_path("kg", "nodes.csv")))
    parser.add_argument("--out", default=str(data_path("kg", "nodes.recency.csv")))
    args = parser.parse_args()
    main(args.meta, args.override, args.nodes, args.out)
