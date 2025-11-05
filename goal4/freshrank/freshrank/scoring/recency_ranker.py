"""Recency-aware scoring utilities with regulatory weighting."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from . import regulatory_weight, utils


@dataclass
class RankedDocument:
    doc_id: str
    chunk_id: Optional[str]
    base_score: float
    recency_multiplier: float
    regulatory_multiplier: float
    regulatory_bonus: float
    w_regulatory: float
    final_score: float
    tags: List[str]
    evidence: List[str]


class RecencyRanker:
    def __init__(self, rules: Dict, weight_config: Dict, tag_index: regulatory_weight.TagIndex):
        self.rules = rules
        self.weight_config = weight_config
        self.tag_index = tag_index

    def score(self, doc: Dict) -> RankedDocument:
        base_score = float(doc.get("relevance", 0.0))
        expired = bool(doc.get("expired", False))
        age_days = utils.days_since(doc.get("effective_date"))
        tier = utils.find_tier(self.rules.get("tiers", []), age_days, expired)
        recency_multiplier = float(tier.get("multiplier", 1.0))
        score = base_score * recency_multiplier

        recency_cfg = self.weight_config.get("recency", {})
        stale_cap = recency_cfg.get("stale_cap")
        if expired and stale_cap is not None:
            score = min(score, stale_cap)

        hits = regulatory_weight.lookup_hits(
            self.tag_index,
            doc.get("doc_id", "unknown"),
            doc.get("chunk_id"),
        )
        adjustment = regulatory_weight.compute_adjustment(hits, self.weight_config)
        score = score * adjustment["multiplier"] + adjustment["bonus"]

        min_score = self.rules.get("expiry_handling", {}).get("min_allowed_score", 0.01)
        auto_demotion = self.rules.get("expiry_handling", {}).get("auto_demotion_score")
        if expired and auto_demotion is not None:
            score = min(score, auto_demotion)
        score = max(min_score, score)

        return RankedDocument(
            doc_id=doc.get("doc_id", "unknown"),
            chunk_id=doc.get("chunk_id"),
            base_score=base_score,
            recency_multiplier=recency_multiplier,
            regulatory_multiplier=adjustment["multiplier"],
            regulatory_bonus=adjustment["bonus"],
            w_regulatory=adjustment["w_regulatory"],
            final_score=score,
            tags=adjustment["tags"],
            evidence=adjustment["evidence"],
        )


def rerank(documents: List[Dict], rules: Dict, weight_config: Dict, tag_index: regulatory_weight.TagIndex) -> List[RankedDocument]:
    ranker = RecencyRanker(rules, weight_config, tag_index)
    scored = [ranker.score(doc) for doc in documents]
    scored.sort(key=lambda d: d.final_score, reverse=True)
    return scored
