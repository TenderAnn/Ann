"""Compute precision/recall/F1 for regulatory tagging outputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import yaml

sys.path.append(str(Path(__file__).resolve().parents[2]))

from regulatory.scripts import eval_utils


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate regulatory tagging quality")
    parser.add_argument("--pred", required=True)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--errors", required=True)
    parser.add_argument("--threshold", type=float, default=0.0, help="Fallback confidence threshold")
    parser.add_argument("--rulebook", default=None, help="Optional rulebook path to read confidence_policy")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    labels = eval_utils.TARGET_TAGS
    thresholds = {label: args.threshold for label in labels}
    if args.rulebook:
        rulebook = yaml.safe_load(Path(args.rulebook).read_text(encoding="utf-8"))
        policy = rulebook.get("confidence_policy", {})
        default = policy.get("default_threshold", args.threshold)
        thresholds = {label: default for label in labels}
        for tag, value in (policy.get("overrides") or {}).items():
            thresholds[tag] = value
    prediction_scores, evidence = eval_utils.load_predictions(Path(args.pred), labels)
    gold = eval_utils.load_gold(Path(args.gold), labels)
    summary, errors = eval_utils.evaluate(prediction_scores, gold, thresholds, labels, evidence)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    eval_utils.write_errors_csv(Path(args.errors), errors)
    print(f"Saved evaluation to {args.out} and errors to {args.errors}")


if __name__ == "__main__":
    main()
