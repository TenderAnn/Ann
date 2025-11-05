from __future__ import annotations

import argparse
import ast
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.utils_norm import (
    BENEFIT_TRIGGER_PATTERNS,
    FIELD_TRIGGER_PATTERNS,
    build_reverse_map,
    detect_version_year,
    first_trigger_hit,
    load_ontology,
    load_synonyms,
    normalize_text,
    rule_slots,
)


def safe_to_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, float) and math.isnan(value):
        return {}
    if isinstance(value, str) and not value.strip():
        return {}
    for loader in (json.loads, ast.literal_eval):
        try:
            loaded = loader(value)
        except Exception:
            continue
        if isinstance(loaded, dict):
            return loaded
    return {}


def _match_specific(trigger_map, key, normalized_text):
    patterns = trigger_map.get(key, [])
    return any(regex.search(normalized_text) for regex in patterns)


def slot_applicable(slot: str, normalized_text: str, gold_value: str) -> bool:
    if slot == "benefit_type":
        if gold_value and _match_specific(BENEFIT_TRIGGER_PATTERNS, gold_value, normalized_text):
            return True
        if gold_value:
            return False
        return first_trigger_hit(BENEFIT_TRIGGER_PATTERNS, normalized_text) is not None
    if slot == "field":
        if gold_value and _match_specific(FIELD_TRIGGER_PATTERNS, gold_value, normalized_text):
            return True
        if gold_value:
            return False
        return first_trigger_hit(FIELD_TRIGGER_PATTERNS, normalized_text) is not None
    if slot == "version_year":
        return detect_version_year(normalized_text) is not None
    return True


def evaluate(
    df: pd.DataFrame,
    ontology_path: Path,
    syn_path: Path,
    mask_by_presence: bool = False,
) -> Dict[str, Dict[str, Any]]:
    ontology = load_ontology(ontology_path)
    reverse_map = build_reverse_map(load_synonyms(syn_path))

    keys = ["product_line", "benefit_type", "field", "version_year"]
    stats = {k: Counter() for k in keys}
    mismatches = defaultdict(list)

    for _, row in df.iterrows():
        query = row.get("colloquial_query", "")
        normalized_query = normalize_text(query, reverse_map)
        gold = safe_to_dict(row.get("slots", {}))
        pred = rule_slots(query, ontology, reverse_map)
        for key in keys:
            gold_val = str(gold.get(key, "")).strip()
            if mask_by_presence and not slot_applicable(key, normalized_query, gold_val):
                continue

            pred_val = str(pred.get(key, "")).strip()
            if gold_val and pred_val:
                if gold_val == pred_val:
                    stats[key]["TP"] += 1
                else:
                    stats[key]["FP"] += 1
                    stats[key]["FN"] += 1
            elif gold_val and not pred_val:
                stats[key]["FN"] += 1
            elif pred_val and not gold_val:
                stats[key]["FP"] += 1

            if len(mismatches[key]) < 5 and (gold_val or pred_val) and gold_val != pred_val:
                mismatches[key].append(
                    {
                        "query": query,
                        "gold": gold_val,
                        "pred": pred_val,
                    }
                )

    report = {}
    for key in keys:
        TP, FP, FN = stats[key]["TP"], stats[key]["FP"], stats[key]["FN"]
        precision = TP / (TP + FP) if (TP + FP) else 0.0
        recall = TP / (TP + FN) if (TP + FN) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        report[key] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "tp": TP,
            "fp": FP,
            "fn": FN,
            "examples": mismatches[key],
        }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate rule-based slot extraction quality.")
    parser.add_argument("--csv", default="data/intent_dataset_zh_insurance_v1.csv")
    parser.add_argument("--ontology", default="data/ontology_insurance_zh.yaml")
    parser.add_argument("--syn", default="data/synonyms_insurance_zh_v1.1.tsv")
    parser.add_argument("--output", default="docs/STEP2_slot_report_v1.1.json")
    parser.add_argument("--mask_by_presence", action="store_true", help="Skip scoring slots without textual triggers.")
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    report = evaluate(
        df,
        Path(args.ontology),
        Path(args.syn),
        mask_by_presence=args.mask_by_presence,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
