#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Evaluate trained intent classifier on a labeled split."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.utils_norm import build_reverse_map, load_synonyms, normalize_text


def load_dataset(csv_path: Path) -> pd.DataFrame:
    return pd.read_csv(csv_path)


def main(args: argparse.Namespace) -> None:
    artifacts = joblib.load("models/intent_baseline.joblib")
    vectorizer = artifacts["vectorizer"]
    classifier = artifacts["classifier"]
    labels = artifacts["labels"]
    label_encoder = artifacts.get("label_encoder")
    syn_path = artifacts["synonyms"]

    rev_map = build_reverse_map(load_synonyms(syn_path))

    df = load_dataset(Path(args.test))
    texts = [normalize_text(str(q), rev_map) for q in df["colloquial_query"].astype(str).tolist()]
    y_true = df["intent"].astype(str).to_numpy()

    X = vectorizer.transform(texts)
    y_pred_enc = classifier.predict(X)
    if label_encoder is not None:
        y_pred = label_encoder.inverse_transform(y_pred_enc)
    else:
        y_pred = y_pred_enc

    acc = accuracy_score(y_true, y_pred)
    print(f"TEST Acc: {acc:.4f}")

    docs_dir = Path("docs")
    docs_dir.mkdir(parents=True, exist_ok=True)

    report = classification_report(y_true, y_pred, digits=4, labels=labels)
    (docs_dir / "intent_cls_report_test.txt").write_text(report, encoding="utf-8")

    cm = confusion_matrix(y_true, y_pred, labels=labels)
    fig = plt.figure(figsize=(8, 6))
    plt.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    plt.title("Confusion Matrix")
    plt.colorbar()
    tick_marks = np.arange(len(labels))
    plt.xticks(tick_marks, labels, rotation=45)
    plt.yticks(tick_marks, labels)
    plt.ylabel("True label")
    plt.xlabel("Predicted label")
    plt.tight_layout()
    fig.savefig(docs_dir / "confusion_matrix_test.png", dpi=160)
    plt.close(fig)

    mis = df[y_true != y_pred].copy()
    mis["pred_intent"] = y_pred[y_true != y_pred]
    mis.to_csv(docs_dir / "intent_misclassified.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate intent classifier")
    parser.add_argument("--test", default="data/splits/test.csv")
    main(parser.parse_args())
