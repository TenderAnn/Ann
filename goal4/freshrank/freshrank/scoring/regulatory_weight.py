"""Helpers to load regulatory tags and compute weighting adjustments."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple
import json


@dataclass
class RegulatoryHit:
    tag: str
    confidence: float
    evidence: List[str]


TagIndex = Dict[Tuple[str, Optional[str]], List[RegulatoryHit]]


def load_tag_index(path: Path) -> TagIndex:
    if not path.exists():
        return {}
    index: TagIndex = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            key = (record.get("doc_id"), record.get("chunk_id"))
            details = record.get("tag_details") or []
            hits = [
                RegulatoryHit(
                    tag=detail.get("name") or detail.get("tag") or tag,
                    confidence=float(detail.get("confidence", record.get("confidence", 0.5))),
                    evidence=detail.get("evidence") or record.get("evidence") or [],
                )
                for tag, detail in _expand_details(record)
            ]
            # Fallback: if no details, treat aggregate tags equally
            if not hits:
                for tag in record.get("tags", []):
                    hits.append(
                        RegulatoryHit(tag=tag, confidence=float(record.get("confidence", 0.5)), evidence=record.get("evidence", []))
                    )
            if hits:
                index[key] = hits
    return index


def _expand_details(record: dict) -> Iterator[Tuple[str, dict]]:
    details = record.get("tag_details") or []
    if isinstance(details, list):
        for item in details:
            if isinstance(item, dict):
                yield item.get("name") or item.get("tag"), item


def lookup_hits(index: TagIndex, doc_id: str, chunk_id: Optional[str]) -> List[RegulatoryHit]:
    if not index:
        return []
    if (doc_id, chunk_id) in index:
        return index[(doc_id, chunk_id)]
    if chunk_id is not None and (doc_id, None) in index:
        return index[(doc_id, None)]
    return index.get((doc_id, chunk_id), [])


def compute_adjustment(
    hits: List[RegulatoryHit],
    weight_config: dict,
) -> dict:
    if not hits:
        return {"multiplier": 1.0, "bonus": 0.0, "tags": [], "evidence": [], "w_regulatory": 0.0}

    evidence: List[str] = []
    tags: List[str] = []
    multiplier = 1.0
    bonus = 0.0
    reg_cfg = weight_config.get("regulatory", {})
    esg_multiplier = reg_cfg.get("esg_multiplier", 1.0)
    rating_bonus = reg_cfg.get("rating_bonus", 0.0)
    max_bonus = reg_cfg.get("max_bonus", rating_bonus)

    for hit in hits:
        tags.append(hit.tag)
        evidence.extend(hit.evidence[:2])
        if hit.tag == "esg":
            multiplier *= esg_multiplier
        if hit.tag == "rating":
            bonus += rating_bonus * hit.confidence

    bonus = min(max_bonus, bonus)
    w_regulatory = (multiplier - 1.0) + bonus
    return {
        "multiplier": multiplier,
        "bonus": bonus,
        "tags": sorted(set(tags)),
        "evidence": evidence,
        "w_regulatory": w_regulatory,
    }
