"""Query rewrite engine based on canonical templates."""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Sequence, Tuple

PLACEHOLDER_RE = re.compile(r"{([^{}]+)}")

FIELD_INTENT_MAP = {
    "投保年龄": "ELIGIBILITY",
    "职业类别": "ELIGIBILITY",
    "交费年期": "PREMIUM_RATE",
    "保障期间": "POLICY_VALIDITY",
    "等待期": "POLICY_VALIDITY",
    "犹豫期": "POLICY_VALIDITY",
    "理赔流程": "CLAIM_PROCESS",
    "理赔材料": "CLAIM_PROCESS",
    "保费/费率": "PREMIUM_RATE",
    "保险金额": "POLICY_VALIDITY",
}


def _fill_template(template: str, slots: Dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return slots.get(key, "")

    text = PLACEHOLDER_RE.sub(repl, template)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _infer_intent_from_slots(slots: Dict[str, str]) -> str | None:
    if slots.get("benefit_type"):
        return "BENEFIT_RETURN"
    field = slots.get("field")
    if field and field in FIELD_INTENT_MAP:
        return FIELD_INTENT_MAP[field]
    if slots.get("product_line"):
        return "POLICY_VALIDITY"
    return None


def _candidate_valid(text: str, required: Iterable[str], slots: Dict[str, str]) -> bool:
    for key in required:
        value = (slots.get(key) or "").strip()
        if value and value not in text:
            return False
    return True


def rewrite_by_templates(
    intent: str | None,
    slots: Dict[str, str],
    templates: Sequence[Dict[str, Iterable[str]]],
    limit: int = 2,
) -> Tuple[List[str], Dict[str, object]]:
    """Generate canonical rewrites using intent-scoped templates."""
    inferred_intent = intent or _infer_intent_from_slots(slots)
    candidate_templates = [
        tmpl for tmpl in templates if not inferred_intent or tmpl.get("intent") == inferred_intent
    ]
    fallback_mode = False
    if not candidate_templates:
        candidate_templates = list(templates)
        fallback_mode = True

    candidates: List[str] = []
    used_templates = 0
    for tmpl in candidate_templates:
        required = tmpl.get("slots_required", []) or []
        if any(not slots.get(slot) for slot in required):
            continue
        filled = _fill_template(tmpl.get("template", ""), slots)
        if not filled or not _candidate_valid(filled, required, slots):
            continue
        used_templates += 1
        candidates.append(filled)
        if len(candidates) >= limit:
            break

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for text in candidates:
        if text not in seen:
            seen.add(text)
            unique.append(text)

    if not unique:
        unique = ["请补充险种、权益或字段信息，以便定位规范问句。"]

    diagnostics = {
        "intent_requested": intent,
        "intent_used": inferred_intent,
        "fallback_mode": fallback_mode,
        "slots": slots,
        "templates_considered": used_templates,
        "generated": len(unique),
    }
    return unique, diagnostics


__all__ = ["rewrite_by_templates"]
