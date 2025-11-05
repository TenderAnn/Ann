from fastapi import FastAPI

from .fusion import run as fusion_run
from .graph_backend import query as graph_query
from .models import PlanOut, QueryIn
from .services.intent_client import parse as intent_parse
from .services.intent_client import rewrite as intent_rewrite

app = FastAPI(title="kg-fusion", version="0.3.0")


@app.get("/healthz")
def healthz():
    return {"ok": True}


def derive_graph_filters(intent: str | None, slots: dict | None) -> dict:
    """Map slots into downstream graph/vector filters (placeholder logic)."""
    slots = slots or {}
    filters: dict = {}
    for key in ("product_name", "product_line", "version_year", "benefit_type", "field"):
        value = slots.get(key)
        if isinstance(value, str) and value.strip():
            filters[key] = value.strip()
    if intent:
        filters["intent"] = intent
    return filters


@app.post("/kg/query", response_model=PlanOut)
async def kg_query(payload: QueryIn):
    parse_result = await intent_parse(payload.text)
    intent = payload.intent or parse_result.get("intent")
    slots = payload.slots or parse_result.get("slots") or {}
    confidence = parse_result.get("confidence")
    threshold = parse_result.get("threshold")
    need_clarify = bool(parse_result.get("need_clarify"))
    should_clarify = need_clarify
    if isinstance(confidence, (int, float)) and isinstance(threshold, (int, float)):
        should_clarify = should_clarify or confidence < threshold

    rewrite_result = await intent_rewrite(payload.text, intent=intent, slots=slots)
    rewrites = rewrite_result.get("rewrites", []) or []
    normalized = parse_result.get("normalized")
    if not rewrites and isinstance(normalized, str):
        rewrites = [normalized]

    filters = derive_graph_filters(intent, slots)
    plan = {
        "graph_filters": filters,
        "query_texts": [payload.text] + rewrites[:2],
        "strategy": ["graph-first", "vector-fallback"],
        "clarify": should_clarify,
    }
    results = fusion_run(filters, plan["query_texts"], topk=20)

    return PlanOut(
        ok=True,
        intent=intent,
        slots=slots,
        confidence=confidence,
        threshold=threshold,
        canonical_candidates=rewrites,
        need_clarify=should_clarify,
        plan=plan,
        results=results,
        debug={
            "parse_raw": parse_result,
            "rewrite_raw": rewrite_result,
            "graph_hits": graph_query(filters).get("hits", []),
        },
    )
