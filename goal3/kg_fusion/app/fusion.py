"""Fusion strategy combining graph hits, vector search, and recency boosts."""
from __future__ import annotations

from typing import Dict, List, Tuple

from .graph_backend import query as graph_query
from .recency import load_recency, recency_score
from .vector_backend import search as vector_search

RECENCY_META = load_recency()

# Weights for final score
W_GRAPH = 0.6
W_SEMANTIC = 0.4


def _collect_graph_hits(filters: Dict[str, str]) -> List[Dict]:
    graph_hits = graph_query(filters).get("hits", [])
    evidence: List[Dict] = []
    for hit in graph_hits:
        for anchor in hit.get("anchors", []):
            evidence.append(
                {
                    "doc_id": anchor.get("doc_id"),
                    "page_no": anchor.get("page_no"),
                    "bbox": anchor.get("bbox"),
                    "preview": (anchor.get("text") or "")[:240],
                    "edge": hit.get("edge"),
                    "source": hit.get("node_type"),
                    "score_graph": 1.0,
                    "score_semantic": 0.0,
                }
            )
    return evidence


def _collect_vector_hits(query_texts: List[str], topk: int) -> List[Dict]:
    vec_hits = vector_search(query_texts, topk=topk)
    results = []
    for hit in vec_hits:
        results.append(
            {
                "doc_id": hit.get("doc_id"),
                "page_no": hit.get("page_no"),
                "bbox": hit.get("bbox"),
                "preview": hit.get("text"),
                "edge": hit.get("type"),
                "source": hit.get("type"),
                "score_graph": 0.0,
                "score_semantic": hit.get("score_semantic", 0.0),
            }
        )
    return results


def run(filters: Dict[str, str], query_texts: List[str], topk: int = 20) -> List[Dict]:
    graph_items = _collect_graph_hits(filters)
    vector_items = _collect_vector_hits(query_texts, topk)

    merged: Dict[Tuple, Dict] = {}

    def key(item: Dict) -> Tuple:
        return (
            item.get("doc_id"),
            tuple(item.get("bbox", [])) if isinstance(item.get("bbox"), list) else item.get("bbox"),
            item.get("preview"),
        )

    for item in graph_items + vector_items:
        k = key(item)
        existing = merged.get(k, {"score_graph": 0.0, "score_semantic": 0.0})
        existing.update({k2: v for k2, v in item.items() if v is not None})
        existing["score_graph"] = max(existing["score_graph"], item.get("score_graph", 0.0))
        existing["score_semantic"] = max(existing["score_semantic"], item.get("score_semantic", 0.0))
        merged[k] = existing

    results: List[Dict] = []
    for item in merged.values():
        doc_id = item.get("doc_id", "")
        recency_meta = RECENCY_META.get(doc_id, {})
        bonus, flags = recency_score(recency_meta)
        score_total = (
            W_GRAPH * item.get("score_graph", 0.0)
            + W_SEMANTIC * item.get("score_semantic", 0.0)
            + bonus
        )
        item["score_recency"] = bonus
        item["recency_flags"] = flags
        item["score_total"] = round(float(score_total), 4)
        results.append(item)

    results.sort(key=lambda x: x["score_total"], reverse=True)
    return results[:topk]
