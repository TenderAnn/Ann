# -*- coding: utf-8 -*-
"""Build minimal KG nodes/edges/anchors from parsed sections and tables."""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Dict, Iterable

from kg_fusion.paths import data_path

KW = {
    "COVERAGE": ["保险责任", "保障责任", "责任范围", "coverage", "benefit"],
    "EXCLUSION": ["免责", "责任免除", "除外责任", "exclusion", "excluded"],
    "ELIGIBILITY": ["投保年龄", "投保规则", "适用人群", "职业类别", "eligibility", "age limit", "等待期", "犹豫期"],
    "CLAIM_MATERIAL": ["理赔材料", "申请材料", "理赔须知", "claim material", "claim document"],
}

HEADER_CANON_MAP = {
    "age": "age",
    "waiting_period": "waiting_period",
    "cooling_off": "cooling_off",
    "annual_premium": "annual_premium",
    "monthly_premium": "monthly_premium",
    "sum_assured": "sum_assured",
    "rate": "rate",
    "premium": "premium",
    "coverage_term": "coverage_term",
    "occupation_class": "occupation_class",
    "product_name": "product_name",
    "version_year": "version_year",
}


def load_jsonl(path: Path) -> Iterable[Dict]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def classify_section(text: str, heading_path: str) -> str | None:
    hay = f"{heading_path or ''} {text or ''}".lower()
    for label, keywords in KW.items():
        if any(k.lower() in hay for k in keywords):
            return label
    return None


def sanitize_id(raw: str) -> str:
    return re.sub(r"[^a-zA-Z0-9:_-]+", "_", raw)[:120]


def create_product_version(doc_id: str) -> tuple[str, str, Dict]:
    node_id = f"pv:{sanitize_id(doc_id)}"
    return node_id, "ProductVersion", {"doc_id": doc_id}


def main(sections_dir: str, tables_dir: str, out_dir: str) -> None:
    sections_dir = Path(sections_dir)
    tables_dir = Path(tables_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    nodes: list[tuple[str, str, Dict]] = []
    edges: list[tuple[str, str, str, Dict]] = []
    anchors: list[Dict] = []
    seen_nodes: set[str] = set()

    def base_name(path: Path, suffix: str) -> str:
        stem = path.stem
        return stem.replace(suffix, "") if stem.endswith(suffix) else stem

    doc_ids = {base_name(p, ".sections") for p in sections_dir.glob("*.sections.jsonl")}
    for doc_id in sorted(doc_ids):
        node = create_product_version(doc_id)
        nodes.append(node)
        seen_nodes.add(node[0])

    for path in sections_dir.glob("*.sections.jsonl"):
        doc_id = base_name(path, ".sections")
        pv_id = f"pv:{sanitize_id(doc_id)}"
        for sec in load_jsonl(path):
            label = classify_section(sec.get("text", ""), sec.get("heading_path", ""))
            if not label:
                continue
            clause_id = f"clause:{sanitize_id(sec['section_id'])}"
            if clause_id not in seen_nodes:
                nodes.append((clause_id, "Clause", {"label": label, "doc_id": doc_id}))
                edges.append((pv_id, f"HAS_{label}", clause_id, {}))
                seen_nodes.add(clause_id)
            anchors.append({
                "node_id": clause_id,
                "source_type": "section",
                "doc_id": doc_id,
                "page_no": sec.get("page_no"),
                "bbox": sec.get("bbox"),
                "text": sec.get("text", "")[:500],
            })

    for path in tables_dir.glob("*.tables.jsonl"):
        doc_id = base_name(path, ".tables")
        pv_id = f"pv:{sanitize_id(doc_id)}"
        for table in load_jsonl(path):
            node_id = f"rt:{sanitize_id(table['table_id'])}"
            header_map = table.get("header_map", {})
            canonical = {int(k): HEADER_CANON_MAP.get(v, v) for k, v in header_map.items()} if header_map else {}
            nodes.append((node_id, "PremiumRateTable", {
                "doc_id": doc_id,
                "page_no": table.get("page_no"),
                "n_rows": table.get("n_rows"),
                "n_cols": table.get("n_cols"),
                "header_map": canonical,
            }))
            edges.append((pv_id, "HAS_RATE_TABLE", node_id, {}))
            anchors.append({
                "node_id": node_id,
                "source_type": "table",
                "doc_id": doc_id,
                "page_no": table.get("page_no"),
                "bbox": table.get("bbox"),
                "text": "",
            })

    nodes_csv = out_dir / "nodes.csv"
    edges_csv = out_dir / "edges.csv"
    anchors_jl = out_dir / "anchors.jsonl"
    with nodes_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["node_id", "node_type", "props_json"])
        for nid, ntype, props in nodes:
            writer.writerow([nid, ntype, json.dumps(props, ensure_ascii=False)])
    with edges_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["src_id", "edge_type", "dst_id", "props_json"])
        for src, etype, dst, props in edges:
            writer.writerow([src, etype, dst, json.dumps(props, ensure_ascii=False)])
    with anchors_jl.open("w", encoding="utf-8") as fh:
        for anc in anchors:
            fh.write(json.dumps(anc, ensure_ascii=False) + "\n")

    print(f"Wrote {nodes_csv}, {edges_csv}, {anchors_jl}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sections_dir", default=str(data_path("parsed")))
    parser.add_argument("--tables_dir", default=str(data_path("tables")))
    parser.add_argument("--out_dir", default=str(data_path("kg")))
    args = parser.parse_args()
    main(args.sections_dir, args.tables_dir, args.out_dir)
