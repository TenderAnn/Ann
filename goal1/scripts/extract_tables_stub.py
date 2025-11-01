"""Detect table-like pages and store PNG snapshots for later processing."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

import fitz  # type: ignore
import yaml
from loguru import logger


KEYWORD_PATTERN = re.compile(r"(表|费率|单位|年龄|缴费|年限)")


def load_cfg(cfg_path: Path) -> Dict:
    with cfg_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main() -> None:
    cfg = load_cfg(Path("configs/config.yaml"))
    paths = cfg.get("paths", {})
    interim_root = Path(paths.get("interim_dir") or "data/interim")
    raw_root = Path(paths.get("raw_dir") or "data/raw")
    tables_root = Path(paths.get("tables_dir") or "corpus/tables")
    tables_root.mkdir(parents=True, exist_ok=True)

    index_records: List[Dict] = []

    for doc_dir in sorted(interim_root.iterdir()):
        if not doc_dir.is_dir():
            continue
        meta_path = doc_dir / "doc_meta.json"
        if not meta_path.exists():
            continue

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        rel_path = meta.get("relative_path")
        file_name = meta.get("file")

        pdf_path = None
        if rel_path:
            candidate = raw_root / rel_path
            if candidate.exists():
                pdf_path = candidate
        if pdf_path is None and file_name:
            matches = list(raw_root.rglob(file_name))
            if matches:
                pdf_path = matches[0]

        if not pdf_path or not pdf_path.exists():
            logger.warning(f"PDF not found for {doc_dir.name}")
            continue

        try:
            doc = fitz.open(pdf_path)
        except Exception as exc:
            logger.warning(f"Unable to open {pdf_path}: {exc}")
            continue

        try:
            for page_json in sorted(doc_dir.glob("page_*.json"), key=lambda p: int(p.stem.split("_")[1])):
                info = json.loads(page_json.read_text(encoding="utf-8"))
                text = info.get("text") or ""
                matches = KEYWORD_PATTERN.findall(text)
                if not matches:
                    continue

                page_no = info.get("page_no", 0)
                if not isinstance(page_no, int) or page_no <= 0 or page_no > doc.page_count:
                    continue

                page = doc.load_page(page_no - 1)
                pix = page.get_pixmap(dpi=144)

                doc_tables_dir = tables_root / doc_dir.name
                doc_tables_dir.mkdir(parents=True, exist_ok=True)
                out_path = doc_tables_dir / f"page_{page_no}.png"
                pix.save(out_path.as_posix())

                index_records.append(
                    {
                        "doc_id": doc_dir.name,
                        "page_no": page_no,
                        "keywords": list(sorted(set(matches))),
                        "png_path": out_path.as_posix(),
                        "pdf_path": pdf_path.as_posix(),
                    }
                )
        finally:
            doc.close()

    index_path = tables_root / "tables_index.json"
    index_path.write_text(json.dumps(index_records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {len(index_records)} table-like pages")


if __name__ == "__main__":
    main()

