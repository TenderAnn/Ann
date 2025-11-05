"""Build sentence-transformer embeddings and hnswlib index for sections and table cells."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List

import hnswlib
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from kg_fusion.paths import data_path


def iter_sections(parsed_dir: Path):
    for file in parsed_dir.glob("*.sections.jsonl"):
        with file.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                sec = json.loads(line)
                text = f"{sec.get('heading_path','')} {sec.get('text','')}".strip()
                if not text:
                    continue
                yield {
                    "chunk_id": f"sec:{sec['section_id']}",
                    "doc_id": sec["doc_id"],
                    "page_no": sec["page_no"],
                    "bbox": sec["bbox"],
                    "text": text,
                    "type": "section",
                }


def iter_table_cells(tables_dir: Path):
    for file in tables_dir.glob("*.tables.jsonl"):
        with file.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                table = json.loads(line)
                for cell in table.get("cells", []):
                    text = (cell.get("text") or "").strip()
                    if not text:
                        continue
                    yield {
                        "chunk_id": f"cell:{table['table_id']}:{cell['row']}:{cell['col']}",
                        "doc_id": table["doc_id"],
                        "page_no": table["page_no"],
                        "bbox": table["bbox"],
                        "text": text,
                        "type": "cell",
                    }


def main(parsed_dir: str, tables_dir: str, out_dir: str, model_name: str, efc: int, m: int) -> None:
    parsed_path = Path(parsed_dir)
    tables_path = Path(tables_dir)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    chunks: List[Dict] = list(iter_sections(parsed_path)) + list(iter_table_cells(tables_path))
    texts = [c["text"] for c in chunks]
    model = SentenceTransformer(model_name)
    embeddings = model.encode(texts, batch_size=64, show_progress_bar=False, normalize_embeddings=True)
    dim = embeddings.shape[1]

    index = hnswlib.Index(space="cosine", dim=dim)
    index.init_index(max_elements=len(chunks), ef_construction=efc, M=m)
    index.add_items(embeddings, np.arange(len(chunks)))
    index.set_ef(64)

    index_path = out_path / "vec.index"
    meta_path = out_path / "vec.meta.csv"
    info_path = out_path / "ann_stats.json"
    index.save_index(str(index_path))
    pd.DataFrame(chunks).to_csv(meta_path, index=False)

    stats = {
        "vectors": len(chunks),
        "dim": dim,
        "model": model_name,
        "index": str(index_path),
        "meta": str(meta_path),
    }
    info_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--parsed_dir", default=str(data_path("parsed")))
    parser.add_argument("--tables_dir", default=str(data_path("tables")))
    parser.add_argument("--out_dir", default=str(data_path("index")))
    parser.add_argument("--model", default=os.getenv("EMB_MODEL", "BAAI/bge-small-zh-v1.5"))
    parser.add_argument("--efc", type=int, default=100)
    parser.add_argument("--M", type=int, default=16)
    args = parser.parse_args()
    main(args.parsed_dir, args.tables_dir, args.out_dir, args.model, args.efc, args.M)
