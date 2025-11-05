"""FastAPI service exposing intent parsing, rewrite, clarify, and feedback endpoints."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel, Field

from api.rewrite_engine import rewrite_by_templates
from api.utils_norm import (
    build_reverse_map,
    load_ontology,
    load_synonyms,
    normalize_text,
    rule_slots,
)

BASE_DIR = Path(__file__).resolve().parents[1]
MODELS_PATH = BASE_DIR / "models" / "intent_baseline.joblib"
THRESHOLD_PATH = BASE_DIR / "configs" / "intent_threshold.json"
TEMPLATE_PATH = BASE_DIR / "data" / "templates_canonical_zh.json"
ONTOLOGY_PATH = BASE_DIR / "data" / "ontology_insurance_zh.yaml"
FEEDBACK_PATH = BASE_DIR / "data" / "feedback.csv"

# Load artifacts
PACK = joblib.load(MODELS_PATH)
VEC = PACK["vectorizer"]
CLF = PACK["classifier"]
LABEL_ENCODER = PACK.get("label_encoder")
LABELS = list(PACK["labels"])
SYN_PATH = Path(PACK["synonyms"])
REV_MAP = build_reverse_map(load_synonyms(SYN_PATH))
ONTOLOGY = load_ontology(ONTOLOGY_PATH)
TEMPLATES = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))

def _load_threshold() -> float:
    try:
        data = json.loads(THRESHOLD_PATH.read_text(encoding="utf-8"))
        return float(data.get("threshold") or data.get("thr") or 0.77)
    except Exception:
        return 0.77


def _predict_intent(normalized_text: str) -> Dict[str, object]:
    vec = VEC.transform([normalized_text])
    proba = CLF.predict_proba(vec)[0]
    encoded_classes = CLF.classes_
    if LABEL_ENCODER is not None:
        label_map = LABEL_ENCODER.inverse_transform(encoded_classes)
    else:
        label_map = encoded_classes

    best_idx = int(np.argmax(proba))
    intent = label_map[best_idx]
    confidence = float(proba[best_idx])
    probs = {label_map[i]: float(prob) for i, prob in enumerate(proba)}
    return {"intent": intent, "confidence": confidence, "probabilities": probs}


class ParseRequest(BaseModel):
    text: str = Field(..., description="Colloquial query text")


class RewriteRequest(BaseModel):
    text: str
    intent: Optional[str] = None
    slots: Optional[Dict[str, str]] = None


class FeedbackRequest(BaseModel):
    query: str
    chosen_rewrite: Optional[str] = None
    success: int = 0
    clicked_docs: Optional[List[str]] = None
    notes: Optional[str] = None


app = FastAPI(title="Intent Engine", version="1.0.0")


@app.post("/intent/parse")
def parse_intent(payload: ParseRequest) -> Dict[str, object]:
    normalized = normalize_text(payload.text, REV_MAP)
    slots = rule_slots(normalized, ONTOLOGY, REV_MAP)
    pred = _predict_intent(normalized)
    threshold = _load_threshold()
    need_clarify = pred["confidence"] < threshold or not slots
    return {
        "intent": pred["intent"],
        "confidence": pred["confidence"],
        "probabilities": pred["probabilities"],
        "normalized": normalized,
        "slots": slots,
        "need_clarify": need_clarify,
        "threshold": threshold,
    }


@app.post("/intent/rewrite")
def rewrite_intent(payload: RewriteRequest) -> Dict[str, object]:
    normalized = normalize_text(payload.text, REV_MAP)
    slots = payload.slots or rule_slots(normalized, ONTOLOGY, REV_MAP)
    rewrites, diag = rewrite_by_templates(payload.intent, slots, TEMPLATES)
    return {"rewrites": rewrites, "diagnostics": diag, "slots": slots}


@app.post("/intent/clarify")
def clarify(payload: RewriteRequest) -> Dict[str, object]:
    normalized = normalize_text(payload.text, REV_MAP)
    slots = payload.slots or rule_slots(normalized, ONTOLOGY, REV_MAP)
    questions: List[str] = []

    if not slots.get("product_line"):
        questions.append("您关注养老/年金、终身寿险还是重疾/意外险种？")
    if not slots.get("benefit_type"):
        questions.append("偏向查询 CCRC 资格权益、生存金短期返还，还是其他权益？")
    if not slots.get("field"):
        questions.append("想了解投保年龄、等待期、交费年期或理赔材料中的哪一项？")
    if not questions:
        questions.append("是否限定具体产品/版本？例如“臻享年金2024版”。")

    suggestions = []
    if normalized and len(normalized) < len(payload.text):
        suggestions.append(f"建议使用规范表述：{normalized}")

    return {
        "question": questions[0],
        "follow_up": questions[1:3],
        "suggestions": suggestions,
        "slots": slots,
    }


@app.post("/intent/feedback")
def feedback(payload: FeedbackRequest) -> Dict[str, object]:
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = [
        payload.query.replace("\t", " "),
        (payload.chosen_rewrite or "").replace("\t", " "),
        str(payload.success),
        "|".join(payload.clicked_docs or []),
        (payload.notes or "").replace("\t", " "),
    ]
    with FEEDBACK_PATH.open("a", encoding="utf-8") as fh:
        fh.write("\t".join(record) + "\n")
    return {"ok": True}
