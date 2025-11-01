"""PDF layout extraction pipeline without OCR (configurable)."""

from __future__ import annotations

import argparse
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import fitz  # type: ignore
import yaml
from loguru import logger


HEADING_REGEX = re.compile(
    r"^(\d+(\.\d+)*[)．、]?\s*|第[一二三四五六七八九十百]+条|[（(][一二三四五六七八九十]+[)）])"
)


def load_cfg(cfg_path: Path) -> Dict:
    with cfg_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def norm_doc_id(pdf_path: Path, raw_root: Path) -> str:
    rel = pdf_path.relative_to(raw_root)
    base = rel.as_posix().replace("/", "__")
    return os.path.splitext(base)[0]


def iter_pdfs(raw_root: Path) -> Iterable[Path]:
    for pdf in sorted(raw_root.rglob("*.pdf")):
        if pdf.is_file():
            yield pdf


def extract_page_dict(page: fitz.Page, heading_threshold: float) -> Dict:
    raw_dict = page.get_text("dict")
    text = page.get_text("text") or ""
    blocks: List[Dict] = []

    for block in raw_dict.get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        block_text_parts: List[str] = []
        max_font = 0.0
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                txt = span.get("text", "")
                if txt:
                    block_text_parts.append(txt)
                try:
                    size = float(span.get("size", 0.0))
                except (TypeError, ValueError):
                    size = 0.0
                max_font = max(max_font, size)

        block_text = "".join(block_text_parts).strip()
        if not block_text:
            continue

        is_heading = (
            bool(block_text)
            and max_font >= heading_threshold
            and len(block_text) <= 60
            and bool(HEADING_REGEX.match(block_text))
        )
        blocks.append(
            {
                "bbox": block.get("bbox", []),
                "max_font_size": max_font,
                "text": block_text,
                "is_heading": is_heading,
            }
        )

    return {
        "page_no": page.number + 1,
        "width": page.rect.width,
        "height": page.rect.height,
        "text": text,
        "blocks": blocks,
    }


def process_pdf(
    pdf_path: Path,
    raw_root: Path,
    out_root: Path,
    heading_threshold: float,
    force_ocr: bool = False,
) -> Dict:
    doc_id = norm_doc_id(pdf_path, raw_root)
    out_dir = out_root / doc_id
    out_dir.mkdir(parents=True, exist_ok=True)

    meta: Dict[str, Optional[object]] = {
        "file": pdf_path.name,
        "relative_path": pdf_path.relative_to(raw_root).as_posix(),
    }

    if force_ocr:
        logger.warning("force_ocr requested but OCR pipeline not implemented; proceeding with direct text.")

    try:
        with fitz.open(pdf_path) as doc:
            meta["page_count"] = doc.page_count
            for page_index in range(doc.page_count):
                page = doc.load_page(page_index)
                page_dict = extract_page_dict(page, heading_threshold)
                (out_dir / f"page_{page_index + 1}.json").write_text(
                    json.dumps(page_dict, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
    except Exception as exc:
        logger.exception(f"Failed to process {pdf_path}: {exc}")
        meta["error"] = str(exc)

    (out_dir / "doc_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cfg", default="configs/config.yaml", help="Path to config file")
    parser.add_argument("--raw-dir", default=None, help="Override raw directory")
    parser.add_argument("--out-dir", default=None, help="Override interim output directory")
    parser.add_argument("--max-workers", type=int, default=4, help="Thread pool workers")
    parser.add_argument("--force-ocr", action="store_true", help="Force OCR fallback (not implemented)")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.cfg))
    paths = cfg.get("paths", {})
    heading_threshold = float(cfg.get("chunking", {}).get("heading_font_threshold", 14.0))

    raw_root = Path(args.raw_dir or paths.get("raw_dir") or "data/raw")
    out_root = Path(args.out_dir or paths.get("interim_dir") or "data/interim")
    out_root.mkdir(parents=True, exist_ok=True)

    pdfs = list(iter_pdfs(raw_root))
    logger.info(f"Found {len(pdfs)} PDFs under {raw_root}")

    summaries: List[Dict] = []
    with ThreadPoolExecutor(max_workers=max(args.max_workers, 1)) as executor:
        futures = [
            executor.submit(
                process_pdf,
                pdf_path,
                raw_root,
                out_root,
                heading_threshold,
                args.force_ocr,
            )
            for pdf_path in pdfs
        ]
        for future in as_completed(futures):
            summaries.append(future.result())

    total_pages = sum(meta.get("page_count", 0) or 0 for meta in summaries)
    success = sum(1 for meta in summaries if "error" not in meta)

    result = {
        "pdfs_total": len(pdfs),
        "pdfs_success": success,
        "pages_total": total_pages,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

