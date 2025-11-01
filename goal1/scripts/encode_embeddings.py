"""Encode corpus or query texts into vector caches across multiple providers."""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
from tqdm import tqdm

import torch

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - optional dependency
    SentenceTransformer = None

try:
    from transformers import AutoModel, AutoTokenizer
except Exception:  # pragma: no cover - optional dependency
    AutoModel = AutoTokenizer = None

try:  # pragma: no cover - optional dependency
    from openai import OpenAI
except Exception:
    OpenAI = None

try:  # pragma: no cover - optional dependency
    import dashscope
    from dashscope import TextEmbedding
    from http import HTTPStatus
except Exception:
    dashscope = None
    TextEmbedding = None
    HTTPStatus = None

try:  # pragma: no cover - optional dependency
    import dashscope
    from dashscope import TextEmbedding
except Exception:
    dashscope = None
    TextEmbedding = None


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def select_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    denom = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-12
    return vectors / denom


def mean_pool(last_hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    masked = last_hidden_state * mask
    summed = torch.sum(masked, dim=1)
    counts = torch.clamp(mask.sum(dim=1), min=1e-9)
    return summed / counts


def embed_sentence_transformers(
    texts: Sequence[str], model_name: str, device: str, batch_size: int
) -> np.ndarray:
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers is required for this provider")
    model = SentenceTransformer(model_name, device=device)
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=False,
    )
    return embeddings.astype(np.float32)


def embed_hf(
    texts: Sequence[str],
    model_name: str,
    device: str,
    max_length: int,
    precision: str,
) -> np.ndarray:
    if AutoModel is None or AutoTokenizer is None:
        raise RuntimeError("transformers is required for this provider")

    torch_dtype = None
    if device == "cuda" and precision in {"bfloat16", "float16"}:
        torch_dtype = torch.bfloat16 if precision == "bfloat16" else torch.float16

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModel.from_pretrained(model_name, trust_remote_code=True, torch_dtype=torch_dtype)
    model.to(device)
    model.eval()

    outputs: List[np.ndarray] = []
    batch_size = 16
    with torch.no_grad():
        for start in tqdm(range(0, len(texts), batch_size), desc=f"HF[{model_name}]"):
            batch = texts[start : start + batch_size]
            tokens = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            )
            tokens = {key: value.to(device) for key, value in tokens.items()}
            last_hidden_state = model(**tokens).last_hidden_state
            pooled = mean_pool(last_hidden_state, tokens["attention_mask"]).cpu().float().numpy()
            outputs.append(pooled)
    return np.concatenate(outputs, axis=0).astype(np.float32)


def embed_openai(texts: Sequence[str], model_name: str, api_key: str) -> np.ndarray:
    if OpenAI is None:
        raise RuntimeError("openai package not installed; run `pip install openai`")
    if not api_key:
        raise RuntimeError("OpenAI API key not provided; use --openai-api-key or set OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)
    results: List[np.ndarray] = []
    batch_size = 100
    for start in tqdm(range(0, len(texts), batch_size), desc=f"OpenAI[{model_name}]"):
        batch = texts[start : start + batch_size]
        response = client.embeddings.create(model=model_name, input=list(batch))
        chunk = np.array([record.embedding for record in response.data], dtype=np.float32)
        results.append(chunk)
    return np.concatenate(results, axis=0)


def embed_dashscope(
    texts: Sequence[str],
    model_name: str,
    api_key: str,
    batch_size: int,
    max_retries: int = 3,
) -> np.ndarray:
    if dashscope is None or TextEmbedding is None:
        raise RuntimeError("dashscope package not installed; run `pip install dashscope`")
    if api_key:
        dashscope.api_key = api_key
    elif not getattr(dashscope, "api_key", None):
        raise RuntimeError("DashScope API key not provided; use --dashscope-api-key or set DASHSCOPE_API_KEY")

    vectors: List[np.ndarray] = []
    for start in tqdm(range(0, len(texts), batch_size), desc=f"DashScope[{model_name}]"):
        batch = texts[start : start + batch_size]
        if not batch:
            continue

        for attempt in range(max_retries):
            try:
                response = TextEmbedding.call(model=model_name, input=list(batch))
                status_code = getattr(response, "status_code", None)
                if status_code is None and isinstance(response, dict):
                    status_code = response.get("status_code")
                if status_code not in (None, getattr(HTTPStatus, "OK", 200), 200):
                    message = getattr(response, "message", None) or response.get("message") if isinstance(response, dict) else ""
                    raise RuntimeError(f"DashScope error status={status_code}, message={message}")

                if hasattr(response, "output") and response.output:
                    embeddings_data = response.output.get("embeddings", [])
                elif isinstance(response, dict):
                    embeddings_data = response.get("output", {}).get("embeddings", [])
                else:
                    embeddings_data = []

                if not embeddings_data:
                    raise RuntimeError("DashScope response missing embeddings")

                batch_vectors = np.array(
                    [np.array(entry.get("embedding"), dtype=np.float32) for entry in embeddings_data],
                    dtype=np.float32,
                )
                vectors.append(batch_vectors)
                break
            except Exception as exc:  # pragma: no cover - retry
                if attempt == max_retries - 1:
                    raise RuntimeError(f"DashScope embedding failed: {exc}") from exc
                time.sleep(2 ** attempt)

    return np.concatenate(vectors, axis=0) if vectors else np.zeros((0, 0), dtype=np.float32)


def infer_split_name(input_path: Path) -> str:
    name = input_path.name.lower()
    if any(token in name for token in ["query", "queries", "qid"]):
        return "queries"
    return "corpus"


def determine_provider(model: str, requested: str) -> str:
    if requested != "auto":
        return requested
    lower = model.lower()
    if lower.startswith(("baai/", "moka-ai/", "sentence-transformers/")):
        return "sentence_transformers"
    if lower.startswith(("gte", "alibaba-nlp/", "qwen")):
        return "hf"
    if lower.startswith("text-embedding-v"):
        return "dashscope"
    if lower.startswith("text-embedding-"):
        return "openai"
    return "sentence_transformers"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--field", required=True)
    parser.add_argument("--id-field", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-alias", required=True)
    parser.add_argument(
        "--provider",
        default="auto",
        choices=["auto", "sentence_transformers", "hf", "openai", "dashscope"],
    )
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--precision", default="float32", choices=["float32", "bfloat16", "float16"])
    parser.add_argument("--normalize", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--openai-api-key", default=None, help="API key for OpenAI provider (optional; overrides env)")
    parser.add_argument("--dashscope-api-key", default=None, help="API key for DashScope provider (optional; overrides env)")
    args = parser.parse_args()

    input_path = Path(args.input)
    records = load_jsonl(input_path)
    if args.limit and args.limit > 0:
        records = records[: args.limit]

    texts = [record.get(args.field, "") for record in records]
    split = infer_split_name(input_path)
    device = select_device()
    provider = determine_provider(args.model, args.provider)
    print(f"Device: {device} | Provider: {provider} | Model: {args.model} | N={len(texts)}")

    embed_start = time.time()
    if provider == "sentence_transformers":
        vectors = embed_sentence_transformers(texts, args.model, device, args.batch_size)
    elif provider == "hf":
        vectors = embed_hf(texts, args.model, device, args.max_length, args.precision)
    elif provider == "openai":
        api_key = args.openai_api_key or os.getenv("OPENAI_API_KEY", "")
        vectors = embed_openai(texts, args.model, api_key)
    elif provider == "dashscope":
        api_key = args.dashscope_api_key or os.getenv("DASHSCOPE_API_KEY", "")
        vectors = embed_dashscope(texts, args.model, api_key, args.batch_size)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    if args.normalize:
        vectors = l2_normalize(vectors)

    elapsed = time.time() - embed_start
    throughput = len(texts) / max(elapsed, 1e-6)
    print(f"Encoded shape: {vectors.shape} | time={elapsed:.2f}s | {throughput:.1f} samples/s")

    rows: List[Dict[str, Any]] = []
    for idx, record in enumerate(records):
        entry = {
            "id": record.get(args.id_field),
            "text": record.get(args.field, ""),
            "vector": vectors[idx].tolist(),
        }
        for key in (
            "doc_id",
            "section_path",
            "page_span",
            "topic",
            "major",
            "prod",
            "qid",
        ):
            if key in record:
                entry[key] = record[key]
        rows.append(entry)

    df = pd.DataFrame(rows)
    output_dir = Path("indexes") / args.model_alias
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{split}.parquet"
    df.to_parquet(output_path, index=False)
    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"Wrote {output_path} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
