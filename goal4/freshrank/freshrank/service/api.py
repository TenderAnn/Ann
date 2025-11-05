"""FastAPI entry point for Freshrank."""
from __future__ import annotations

from collections import Counter, deque
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Header, Query

from .schemas import RankRequest, RankResponse
from .pipeline import RankingPipeline

app = FastAPI(title="Freshrank")
pipeline = RankingPipeline()

REGULATORY_METRICS = {
    "tag_counts": Counter(),
    "w_reg_values": deque(maxlen=1000),
}
W_REG_BINS = [-0.1, 0.0, 0.05, 0.1, 0.2, 1.0]


def _resolve_regulatory_flag(body_flag: str, query_flag: Optional[str], header_flag: Optional[str]) -> bool:
    for flag in (query_flag, header_flag, body_flag):
        if flag is None or flag == "auto":
            continue
        if flag.lower() == "off":
            return False
        if flag.lower() == "on":
            return True
    return True


def _record_metrics(items: list[dict]) -> None:
    for item in items:
        for tag in item.get("tags", []):
            REGULATORY_METRICS["tag_counts"][tag] += 1
        w_reg = float(item.get("score_breakdown", {}).get("w_regulatory", 0.0))
        REGULATORY_METRICS["w_reg_values"].append(w_reg)


def _histogram(values: list[float]) -> list[dict]:
    if not values:
        return []
    bins = []
    for idx in range(len(W_REG_BINS) - 1):
        low, high = W_REG_BINS[idx], W_REG_BINS[idx + 1]
        count = sum(1 for value in values if low <= value < high)
        bins.append({"range": [low, high], "count": count})
    return bins


@app.post("/rerank", response_model=RankResponse)
def rank(
    request: RankRequest,
    regulatory: Optional[str] = Query(None, description="Force regulatory weighting on/off/auto"),
    x_regulatory: Optional[str] = Header(None, convert_underscores=False),
) -> RankResponse:
    use_regulatory = _resolve_regulatory_flag(request.regulatory, regulatory, x_regulatory)
    ranked = pipeline.rank(request.documents, regulatory=use_regulatory)
    _record_metrics(ranked)
    return RankResponse(results=ranked)


@app.post("/admin/reload-config")
def reload_config():
    pipeline.reload()
    return {
        "status": "ok",
        "reloaded_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/metrics/regulatory")
def regulatory_metrics():
    values = list(REGULATORY_METRICS["w_reg_values"])
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "tag_counts": REGULATORY_METRICS["tag_counts"],
        "w_reg_histogram": _histogram(values),
        "sample_size": len(values),
    }


@app.get("/openapi.json", include_in_schema=False)
def openapi_schema():
    """Expose a stable OpenAPI schema for contract freezing."""
    return app.openapi()
