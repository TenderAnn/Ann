"""Grid search confidence thresholds for regulatory tags."""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Dict, List
import sys

import yaml

sys.path.append(str(Path(__file__).resolve().parents[2]))

from regulatory.scripts import eval_utils


def parse_cooccur(value: str | None) -> Dict[str, List[str]]:
    mapping: Dict[str, List[str]] = {}
    if not value:
        return mapping
    pairs = [segment.strip() for segment in value.split(";") if segment.strip()]
    for pair in pairs:
        if ":" not in pair:
            continue
        tag, keywords = pair.split(":", 1)
        mapping[tag.strip()] = [kw.strip() for kw in keywords.split("|") if kw.strip()]
    return mapping


def apply_cooccur_filter(predictions, evidence, mapping):
    if not mapping:
        return predictions
    filtered = deepcopy(predictions)
    for key, tag_scores in list(filtered.items()):
        evid_map = evidence.get(key, {})
        for tag in list(tag_scores.keys()):
            keywords = mapping.get(tag)
            if not keywords:
                continue
            text = " ".join(evid_map.get(tag, []))
            if not any(keyword in text for keyword in keywords):
                del tag_scores[tag]
        if not tag_scores:
            del filtered[key]
    return filtered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run threshold grid search for regulatory tags")
    parser.add_argument("--pred", required=True)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--thresholds", nargs="*", type=float, default=[0.35, 0.45, 0.55, 0.65])
    parser.add_argument("--cooccur", type=str, default="", help="e.g. rating:通报|排名;esg:责任投资|信息披露")
    parser.add_argument("--rulebook", default=None)
    parser.add_argument("--out", required=True)
    parser.add_argument("--no-auto-cooccur", action="store_true", help="Disable auto derivation from rulebook")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    labels = eval_utils.TARGET_TAGS
    prediction_scores, evidence = eval_utils.load_predictions(Path(args.pred), labels)
    gold = eval_utils.load_gold(Path(args.gold), labels)
    cooccur_map = parse_cooccur(args.cooccur)
    if not args.no_auto_cooccur and not cooccur_map and args.rulebook:
        rb = yaml.safe_load(Path(args.rulebook).read_text(encoding="utf-8"))
        for tag, cfg in (rb.get("tagging") or {}).items():
            patterns = cfg.get("cooccur") or []
            regex_terms = []
            for item in patterns:
                if item.get("type") == "regex" and item.get("value"):
                    regex_terms.append(item["value"])
            if regex_terms:
                cooccur_map[tag] = regex_terms
    filtered_predictions = apply_cooccur_filter(prediction_scores, evidence, cooccur_map)

    policy_default = 0.0
    overrides: Dict[str, float] = {}
    if args.rulebook:
        rb = yaml.safe_load(Path(args.rulebook).read_text(encoding="utf-8"))
        policy = rb.get("confidence_policy", {})
        policy_default = policy.get("default_threshold", 0.0)
        overrides = policy.get("overrides", {})

    base_thresholds = {label: overrides.get(label, policy_default) for label in labels}
    grid_results: Dict[str, List[dict]] = {label: [] for label in labels}
    best = {}

    for label in labels:
        for value in args.thresholds:
            thresholds = base_thresholds.copy()
            thresholds[label] = value
            summary, _ = eval_utils.evaluate(filtered_predictions, gold, thresholds, labels, evidence)
            metrics = summary["per_label"].get(label, {})
            row = {"threshold": value, **metrics}
            grid_results[label].append(row)
        best[label] = max(grid_results[label], key=lambda item: item.get("f1", 0.0), default={})

    # Evaluate once with best thresholds combined
    combined_thresholds = {label: best[label].get("threshold", 0.0) for label in labels}
    combined_summary, _ = eval_utils.evaluate(filtered_predictions, gold, combined_thresholds, labels, evidence)

    payload = {
        "grid": grid_results,
        "best": best,
        "combined_thresholds": combined_thresholds,
        "combined_summary": combined_summary,
        "cooccur": cooccur_map,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Threshold tuning saved to {args.out}")


if __name__ == "__main__":
    main()
