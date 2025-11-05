# -*- coding: utf-8 -*-
"""Load KG CSV/JSONL into sqlite and emit stats."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pandas as pd

from kg_fusion.paths import EVAL_ROOT, data_path


def main(in_dir: str, sqlite_path: str, report_path: str) -> None:
    in_dir = Path(in_dir)
    nodes = pd.read_csv(in_dir / "nodes.csv")
    edges = pd.read_csv(in_dir / "edges.csv")
    anchors = [json.loads(line) for line in open(in_dir / "anchors.jsonl", encoding="utf-8") if line.strip()]

    sqlite_path = Path(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(sqlite_path)
    cur = con.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS nodes;
        DROP TABLE IF EXISTS edges;
        DROP TABLE IF EXISTS anchors;
        CREATE TABLE nodes (node_id TEXT PRIMARY KEY, node_type TEXT, props_json TEXT);
        CREATE TABLE edges (src_id TEXT, edge_type TEXT, dst_id TEXT, props_json TEXT);
        CREATE TABLE anchors (
            node_id TEXT,
            doc_id TEXT,
            page_no INTEGER,
            bbox TEXT,
            text TEXT,
            source_type TEXT
        );
        """
    )
    nodes.to_sql("nodes", con, if_exists="append", index=False)
    edges.to_sql("edges", con, if_exists="append", index=False)
    cur.executemany(
        "INSERT INTO anchors(node_id, doc_id, page_no, bbox, text, source_type) VALUES (?,?,?,?,?,?)",
        [
            (
                anc["node_id"],
                anc.get("doc_id"),
                int(anc.get("page_no", 0) or 0),
                json.dumps(anc.get("bbox"), ensure_ascii=False),
                anc.get("text", ""),
                anc.get("source_type"),
            )
            for anc in anchors
        ],
    )
    con.commit()
    con.close()

    stats = {
        "nodes": len(nodes),
        "edges": len(edges),
        "anchors": len(anchors),
        "sqlite": str(sqlite_path),
    }
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--in_dir", default=str(data_path("kg")))
    parser.add_argument("--sqlite", default=str(data_path("kg", "graph.sqlite")))
    parser.add_argument("--report", default=str(EVAL_ROOT / "reports" / "kg_ingest_stats.json"))
    args = parser.parse_args()
    main(args.in_dir, args.sqlite, args.report)
