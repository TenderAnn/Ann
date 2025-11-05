# -*- coding: utf-8 -*-
"""Simple sqlite-backed graph queries"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List

from ..paths import data_path, env_or_path

SQLITE_PATH = env_or_path("KG_SQLITE", data_path("kg", "graph.sqlite"))


def _choose_edges(filters: Dict[str, Any]) -> List[str]:
    edge_types: List[str] = []
    intent = (filters.get("intent") or "").upper()
    field = (filters.get("field") or "").lower()
    if intent == "COVERAGE_EXCLUSION" or "exclusion" in field:
        edge_types.append("HAS_EXCLUSION")
    if intent == "ELIGIBILITY" or "eligib" in field or "等待" in field:
        edge_types.append("HAS_ELIGIBILITY")
    if intent == "CLAIM_PROCESS" or "claim" in field:
        edge_types.append("HAS_CLAIM_MATERIAL")
    if intent == "COVERAGE" or "coverage" in field or "责任" in field:
        edge_types.append("HAS_COVERAGE")
    if intent == "PREMIUM_RATE" or "premium" in field:
        edge_types.append("HAS_RATE_TABLE")
    if not edge_types:
        edge_types = [
            "HAS_COVERAGE",
            "HAS_EXCLUSION",
            "HAS_ELIGIBILITY",
            "HAS_CLAIM_MATERIAL",
            "HAS_RATE_TABLE",
        ]
    return edge_types


def query(filters: Dict[str, Any]) -> Dict[str, Any]:
    edge_types = _choose_edges(filters)
    con = sqlite3.connect(str(SQLITE_PATH))
    cur = con.cursor()

    placeholders = ",".join(["?"] * len(edge_types))
    rows = cur.execute(
        f"""
        SELECT e.edge_type, n.node_id, n.node_type, n.props_json
        FROM edges e
        JOIN nodes n ON n.node_id = e.dst_id
        WHERE e.edge_type IN ({placeholders})
        """,
        edge_types,
    ).fetchall()
    hits = []
    node_ids = []
    for edge_type, node_id, node_type, props_json in rows:
        props = json.loads(props_json)
        hits.append({
            "edge": edge_type,
            "node_id": node_id,
            "node_type": node_type,
            "props": props,
        })
        node_ids.append(node_id)

    anchors: Dict[str, List[Dict[str, Any]]] = {}
    if node_ids:
        placeholders = ",".join(["?"] * len(node_ids))
        for node_id, doc_id, page_no, bbox, text, source_type in cur.execute(
            f"SELECT node_id, doc_id, page_no, bbox, text, source_type FROM anchors WHERE node_id IN ({placeholders})",
            node_ids,
        ):
            anchors.setdefault(node_id, []).append(
                {
                    "doc_id": doc_id,
                    "page_no": page_no,
                    "bbox": json.loads(bbox),
                    "text": text,
                    "source_type": source_type,
                }
            )
    con.close()

    for hit in hits:
        hit["anchors"] = anchors.get(hit["node_id"], [])
    return {"hits": hits}
