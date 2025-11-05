#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Calibrate clarification threshold using validation set."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.utils_norm import build_reverse_map, load_synonyms, normalize_text


def main() -> None:
    artifacts = joblib.load("models/intent_baseline.joblib")
    vectorizer = artifacts["vectorizer"]
    classifier = artifacts["classifier"]
    label_encoder = artifacts.get("label_encoder")
    syn_path = artifacts["synonyms"]

    rev_map = build_reverse_map(load_synonyms(syn_path))

    df = pd.read_csv("data/splits/valid.csv")
    texts = [normalize_text(str(q), rev_map) for q in df["colloquial_query"].astype(str).tolist()]
    labels = df["intent"].astype(str).to_numpy()

    X = vectorizer.transform(texts)
    probs = classifier.predict_proba(X)
    preds_enc = classifier.predict(X)
    if label_encoder is not None:
        preds = label_encoder.inverse_transform(preds_enc)
    else:
        preds = preds_enc
    correct = preds == labels
    max_prob = probs.max(axis=1)

    search_space = np.linspace(0.5, 0.95, 46)
    best = {
        "threshold": 0.0,
        "accept_accuracy": 0.0,
        "reject_rate": 0.0,
        "penalty": 1e9,
    }
    target_low, target_high = 0.10, 0.15
    for thr in search_space:
        accepted = max_prob >= thr
        if accepted.sum() == 0:
            continue
        acc = float(correct[accepted].mean())
        reject_rate = 1.0 - float(accepted.mean())
        if target_low <= reject_rate <= target_high:
            penalty = 0.0
        else:
            penalty = abs(reject_rate - (target_low + target_high) / 2)
        score = acc - 0.05 * penalty
        if score > best["accept_accuracy"] - 0.05 * best["penalty"]:
            best = {
                "threshold": float(thr),
                "accept_accuracy": acc,
                "reject_rate": reject_rate,
                "penalty": penalty,
            }

    configs_dir = Path("configs")
    configs_dir.mkdir(parents=True, exist_ok=True)
    output_path = configs_dir / "intent_threshold.json"
    output_path.write_text(json.dumps(best, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved threshold config to", output_path)
    print(json.dumps(best, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
