"""Ranking pipeline that wires config, regulatory weights, and scorers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from dateutil import parser as date_parser
import yaml

from ..scoring import recency_ranker, regulatory_weight

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
REGULATORY_DIR = Path(__file__).resolve().parents[2] / "regulatory"
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class RankingPipeline:
    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        with open(CONFIG_DIR / "ranking_rules.yaml", "r", encoding="utf-8") as handle:
            self.rules = yaml.safe_load(handle)
        with open(REGULATORY_DIR / "weights.yaml", "r", encoding="utf-8") as handle:
            self.weight_config = yaml.safe_load(handle)
        esg_path = DATA_DIR / "metadata" / "esg_tags.jsonl"
        self.tag_index = regulatory_weight.load_tag_index(esg_path)

    def _normalize_doc(self, doc: dict) -> dict:
        payload = doc.dict() if hasattr(doc, "dict") else dict(doc)
        effective_date = payload.get("effective_date")
        if isinstance(effective_date, str) and effective_date:
            try:
                payload["effective_date"] = date_parser.isoparse(effective_date)
            except ValueError:
                payload["effective_date"] = None
        publish_date = payload.get("publish_date")
        if isinstance(publish_date, str) and publish_date:
            try:
                payload["publish_date"] = date_parser.isoparse(publish_date)
            except ValueError:
                payload["publish_date"] = None
        return payload

    def rank(self, docs: List[dict], *, regulatory: bool = True):
        normalized = [self._normalize_doc(doc) for doc in docs]
        tag_index = self.tag_index if regulatory else {}
        scored = recency_ranker.rerank(normalized, self.rules, self.weight_config, tag_index)
        return [
            {
                "doc_id": item.doc_id,
                "chunk_id": item.chunk_id,
                "final_score": item.final_score,
                "score_breakdown": {
                    "base": item.base_score,
                    "recency_multiplier": item.recency_multiplier,
                    "regulatory_multiplier": item.regulatory_multiplier,
                    "regulatory_bonus": item.regulatory_bonus,
                    "w_regulatory": item.w_regulatory,
                },
                "tags": item.tags,
                "evidence": item.evidence,
            }
            for item in scored
        ]

    def dump_manifest(self, path: Path) -> None:
        payload = {
            "rules": self.rules,
            "weights": self.weight_config,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
