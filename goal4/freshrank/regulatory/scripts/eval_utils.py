"""Shared utilities for regulatory tagging evaluation."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

Key = Tuple[str, Optional[str]]


TARGET_TAGS = [
    "esg",
    "rating",
    "data_security",
    "consumer_protection",
    "sales_compliance",
    "aml",
    "disclosure_gov",
]


def load_predictions(path: Path, allowed_tags: Iterable[str] | None = None):
    allowed = set(allowed_tags) if allowed_tags else None
    scores: Dict[Key, Dict[str, float]] = {}
    evidence: Dict[Key, Dict[str, List[str]]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            key = (payload.get("doc_id"), payload.get("chunk_id"))
            tag_scores: Dict[str, float] = {}
            tag_evidence: Dict[str, List[str]] = {}
            details = payload.get("tag_details") or []
            if details:
                for detail in details:
                    tag = detail.get("name") or detail.get("tag")
                    if not tag:
                        continue
                    if allowed and tag not in allowed:
                        continue
                    confidence = float(detail.get("confidence", payload.get("confidence", 0.5)))
                    tag_scores[tag] = max(tag_scores.get(tag, 0.0), confidence)
                    tag_evidence.setdefault(tag, detail.get("evidence", []) or [])
            else:
                for tag in payload.get("tags", []):
                    if allowed and tag not in allowed:
                        continue
                    confidence = float(payload.get("confidence", 0.5))
                    tag_scores[tag] = max(tag_scores.get(tag, 0.0), confidence)
                    tag_evidence.setdefault(tag, payload.get("evidence", []) or [])
            if tag_scores:
                scores[key] = tag_scores
                evidence[key] = tag_evidence
    return scores, evidence


def load_gold(path: Path, allowed_tags: Iterable[str] | None = None) -> Dict[Key, Set[str]]:
    allowed = set(allowed_tags) if allowed_tags else None
    gold: Dict[Key, Set[str]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            key = (payload.get("doc_id"), payload.get("chunk_id"))
            tags = set(payload.get("tags", []))
            if allowed:
                tags = {tag for tag in tags if tag in allowed}
            gold[key] = tags
    return gold


def evaluate(
    predictions: Dict[Key, Dict[str, float]],
    gold: Dict[Key, Set[str]],
    thresholds: Dict[str, float] | None = None,
    labels: Iterable[str] | None = None,
    evidence: Dict[Key, Dict[str, List[str]]] | None = None,
):
    labels = list(labels or TARGET_TAGS)
    thresholds = thresholds or {}
    evidence = evidence or {}
    counts = {label: {"tp": 0, "fp": 0, "fn": 0} for label in labels}
    errors: List[dict] = []

    all_keys = set(gold.keys()) if gold else set(predictions.keys())
    for key in all_keys:
        pred_map = predictions.get(key, {})
        gold_set = gold.get(key, set())
        filtered_preds = {
            tag
            for tag, score in pred_map.items()
            if score >= thresholds.get(tag, 0.0)
        }
        for tag in labels:
            in_pred = tag in filtered_preds
            in_gold = tag in gold_set
            if in_pred and in_gold:
                counts[tag]["tp"] += 1
            elif in_pred and not in_gold:
                counts[tag]["fp"] += 1
                errors.append(
                    {
                        "doc_id": key[0],
                        "chunk_id": key[1],
                        "tag": tag,
                        "type": "FP",
                        "confidence": pred_map.get(tag, 0.0),
                        "evidence": (evidence.get(key, {}).get(tag)) or [],
                        "gold_tags": sorted(gold_set),
                    }
                )
            elif in_gold and not in_pred:
                counts[tag]["fn"] += 1
                errors.append(
                    {
                        "doc_id": key[0],
                        "chunk_id": key[1],
                        "tag": tag,
                        "type": "FN",
                        "confidence": pred_map.get(tag, 0.0),
                        "evidence": (evidence.get(key, {}).get(tag)) or [],
                        "gold_tags": sorted(gold_set),
                    }
                )

    metrics = {}
    total_tp = total_fp = total_fn = 0
    for tag in labels:
        tp = counts[tag]["tp"]
        fp = counts[tag]["fp"]
        fn = counts[tag]["fn"]
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        metrics[tag] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }
        total_tp += tp
        total_fp += fp
        total_fn += fn

    macro_precision = sum(m["precision"] for m in metrics.values()) / len(labels)
    macro_recall = sum(m["recall"] for m in metrics.values()) / len(labels)
    macro_f1 = sum(m["f1"] for m in metrics.values()) / len(labels)
    micro_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0.0
    micro_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0.0
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if (micro_precision + micro_recall)
        else 0.0
    )

    summary = {
        "macro": {
            "precision": round(macro_precision, 4),
            "recall": round(macro_recall, 4),
            "f1": round(macro_f1, 4),
        },
        "micro": {
            "precision": round(micro_precision, 4),
            "recall": round(micro_recall, 4),
            "f1": round(micro_f1, 4),
            "tp": total_tp,
            "fp": total_fp,
            "fn": total_fn,
        },
        "per_label": metrics,
    }
    return summary, errors


def write_errors_csv(path: Path, errors: List[dict]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["doc_id", "chunk_id", "tag", "type", "confidence", "gold_tags", "evidence"])
        writer.writeheader()
        for row in errors:
            writer.writerow(
                {
                    "doc_id": row.get("doc_id"),
                    "chunk_id": row.get("chunk_id"),
                    "tag": row.get("tag"),
                    "type": row.get("type"),
                    "confidence": row.get("confidence"),
                    "gold_tags": ";".join(row.get("gold_tags", [])),
                    "evidence": " | ".join(row.get("evidence", [])),
                }
            )
