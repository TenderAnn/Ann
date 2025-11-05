#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Train baseline intent classifier using TF-IDF char n-grams + LinearSVC."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import LinearSVC
from sklearn.utils.class_weight import compute_class_weight

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.utils_norm import build_reverse_map, load_synonyms, normalize_text


def load_xy(csv_path: Path, rev_map: dict[str, str]) -> tuple[list[str], list[str]]:
    df = pd.read_csv(csv_path)
    texts = [normalize_text(str(q), rev_map) for q in df["colloquial_query"].astype(str).tolist()]
    labels = df["intent"].astype(str).tolist()
    return texts, labels


def main(args: argparse.Namespace) -> None:
    models_dir = Path("models")
    models_dir.mkdir(parents=True, exist_ok=True)
    docs_dir = Path("docs")
    docs_dir.mkdir(parents=True, exist_ok=True)

    rev_map = build_reverse_map(load_synonyms(args.synonyms))

    X_train, y_train = load_xy(Path(args.train), rev_map)
    X_valid, y_valid = load_xy(Path(args.valid), rev_map)

    vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(2, 4),
        max_features=200_000,
        lowercase=False,
    )
    Xtr = vectorizer.fit_transform(X_train)
    Xva = vectorizer.transform(X_valid)

    label_encoder = LabelEncoder()
    y_train_enc = label_encoder.fit_transform(y_train)
    y_valid_enc = label_encoder.transform(y_valid)

    enc_classes = np.arange(len(label_encoder.classes_))
    class_weights = compute_class_weight(
        class_weight="balanced",
        classes=enc_classes,
        y=y_train_enc,
    )
    class_weight_map = {int(c): weight for c, weight in zip(enc_classes, class_weights)}

    base_clf = LinearSVC(C=1.5, class_weight=class_weight_map, random_state=42)
    clf = CalibratedClassifierCV(estimator=base_clf, method="sigmoid", cv=3)
    clf.fit(Xtr, y_train_enc)

    y_pred_valid_enc = clf.predict(Xva)
    y_pred_valid = label_encoder.inverse_transform(y_pred_valid_enc)
    acc = accuracy_score(y_valid, y_pred_valid)
    print(f"VALID Acc: {acc:.4f}")
    report = classification_report(y_valid, y_pred_valid, digits=4)
    (docs_dir / "intent_cls_report_v1.txt").write_text(report, encoding="utf-8")

    payload = {
        "vectorizer": vectorizer,
        "classifier": clf,
        "labels": label_encoder.classes_.tolist(),
        "label_encoder": label_encoder,
        "synonyms": str(Path(args.synonyms)),
    }
    joblib.dump(payload, models_dir / "intent_baseline.joblib")
    print("Model saved to models/intent_baseline.joblib")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train baseline intent classifier")
    parser.add_argument("--train", default="data/splits/train.csv")
    parser.add_argument("--valid", default="data/splits/valid.csv")
    parser.add_argument("--synonyms", default="data/synonyms_insurance_zh_v1.1.tsv")
    main(parser.parse_args())
