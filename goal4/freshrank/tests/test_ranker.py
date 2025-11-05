from datetime import datetime, timedelta, timezone

from freshrank.scoring import recency_ranker

RULES = {
    "tiers": [
        {"id": "new_release", "max_age_days": 180, "multiplier": 1.3},
        {"id": "active_baseline", "max_age_days": 730, "multiplier": 1.0},
        {"id": "stale", "max_age_days": None, "multiplier": 0.5},
    ],
    "expiry_handling": {"min_allowed_score": 0.01, "auto_demotion_score": 0.05},
}
WEIGHTS = {
    "recency": {"stale_cap": 0.05},
    "regulatory": {"esg_multiplier": 1.15, "rating_bonus": 0.1, "max_bonus": 0.1},
}


def test_rerank_prefers_newer_document(monkeypatch):
    today = datetime.now(timezone.utc)
    docs = [
        {"doc_id": "new", "effective_date": today - timedelta(days=10), "relevance": 1.0},
        {"doc_id": "old", "effective_date": today - timedelta(days=400), "relevance": 1.0},
    ]
    ranked = recency_ranker.rerank(docs, RULES, WEIGHTS, {})
    assert ranked[0].doc_id == "new"
