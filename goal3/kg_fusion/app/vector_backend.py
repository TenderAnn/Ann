"""Vector search backend using sentence-transformers + hnswlib."""
from __future__ import annotations

import ast
import os
from functools import lru_cache
from typing import Dict, List

import hnswlib
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

from ..paths import data_path, env_or_path

INDEX_PATH = env_or_path("VEC_INDEX", data_path("index", "vec.index"))
META_PATH = env_or_path("VEC_META", data_path("index", "vec.meta.csv"))
MODEL_NAME = os.getenv("EMB_MODEL", "BAAI/bge-small-zh-v1.5")


@lru_cache()
def _load_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


@lru_cache()
def _load_index() -> hnswlib.Index:
    model = _load_model()
    dim = model.get_sentence_embedding_dimension()
    index = hnswlib.Index(space="cosine", dim=dim)
    index.load_index(str(INDEX_PATH))
    index.set_ef(64)
    return index


@lru_cache()
def _load_meta() -> pd.DataFrame:
    return pd.read_csv(META_PATH)


def search(query_texts: List[str], topk: int = 20) -> List[Dict]:
    if not query_texts:
        return []
    model = _load_model()
    index = _load_index()
    meta = _load_meta()

    embeddings = model.encode(query_texts, normalize_embeddings=True)
    labels, distances = index.knn_query(embeddings, k=topk)

    hits: Dict[str, Dict] = {}
    for q_idx, q in enumerate(query_texts):
        for label, dist in zip(labels[q_idx], distances[q_idx]):
            if label < 0:
                continue
            row = meta.iloc[int(label)]
            chunk_id = row["chunk_id"]
            sim = 1.0 - float(dist)
            if chunk_id not in hits or sim > hits[chunk_id]["score_semantic"]:
                bbox = row["bbox"]
                if isinstance(bbox, str):
                    try:
                        bbox = ast.literal_eval(bbox)
                    except Exception:
                        bbox = []
                hits[chunk_id] = {
                    "chunk_id": chunk_id,
                    "doc_id": row["doc_id"],
                    "page_no": int(row["page_no"]),
                    "bbox": bbox,
                    "text": row["text"][:240],
                    "type": row.get("type", ""),
                    "score_semantic": sim,
                }
    return list(hits.values())
