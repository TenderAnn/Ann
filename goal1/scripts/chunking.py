"""Heading-aware chunking over interim page JSON artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import yaml
from loguru import logger


HEADER_FOOTER_PAT = re.compile(r"(第\s*\d+\s*页|Page\s*\d+|\s*—\s*\d+\s*—)$")


@dataclass
class PageEntry:
    page_no: int
    text: str


def load_cfg(cfg_path: Path) -> Dict:
    with cfg_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def iter_doc_dirs(interim_root: Path) -> Iterable[Path]:
    for doc_dir in sorted(interim_root.iterdir()):
        if doc_dir.is_dir() and (doc_dir / "doc_meta.json").exists():
            yield doc_dir


def read_page_json(page_path: Path) -> Dict:
    return json.loads(page_path.read_text(encoding="utf-8"))


def norm_page_order(path: Path) -> int:
    return int(path.stem.split("_")[1])


def build_sections(blocks: List[Dict]) -> List[Tuple[bool, str, float]]:
    sections: List[Tuple[bool, str, float]] = []
    for block in blocks:
        text = (block.get("text") or "").strip()
        if not text:
            continue
        if HEADER_FOOTER_PAT.search(text):
            continue
        is_heading = bool(block.get("is_heading"))
        max_font = float(block.get("max_font_size") or 0.0)
        sections.append((is_heading, text, max_font))
    return sections


def clean_page_text(raw_text: str) -> str:
    lines: List[str] = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if HEADER_FOOTER_PAT.search(stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def chunk_text(text: str, max_chars: int, overlap: int) -> List[Tuple[str, int, int]]:
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    length = len(text)
    if length == 0:
        return []
    segments: List[Tuple[str, int, int]] = []
    if length <= max_chars:
        segments.append((text, 0, length))
        return segments

    step = max(1, max_chars - overlap)
    start = 0
    while start < length:
        end = min(length, start + max_chars)
        segments.append((text[start:end], start, end))
        if end == length:
            break
        start += step
    return segments


def hash_id(*parts: str) -> str:
    joined = "||".join(parts)
    return hashlib.md5(joined.encode("utf-8")).hexdigest()[:12]


def pages_for_segment(intervals: Sequence[Tuple[int, int, int]], start: int, end: int) -> List[int]:
    covered: List[int] = []
    for page_no, span_start, span_end in intervals:
        if end <= span_start or start >= span_end:
            continue
        covered.append(page_no)
    return covered


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cfg", default="configs/config.yaml", help="Path to config")
    parser.add_argument("--interim", default=None, help="Override interim input directory")
    parser.add_argument("--out", default=None, help="Override chunks output path")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.cfg))
    paths = cfg.get("paths", {})

    interim_root = Path(args.interim or paths.get("interim_dir") or "data/interim")
    out_path = Path(args.out or paths.get("chunks_out") or "corpus/chunks/all_chunks.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    chunk_cfg = cfg.get("chunking", {})
    max_chars = int(chunk_cfg.get("max_chars", 350))
    overlap_chars = int(chunk_cfg.get("overlap_chars", 120))
    min_para_chars = int(chunk_cfg.get("min_paragraph_chars", 40))
    cross_page_merge = bool(chunk_cfg.get("cross_page_merge", True))

    total_pages = 0
    total_chunks = 0
    pages_with_chunks: set[Tuple[str, int]] = set()

    with out_path.open("w", encoding="utf-8") as writer:
        for doc_dir in iter_doc_dirs(interim_root):
            meta = json.loads((doc_dir / "doc_meta.json").read_text(encoding="utf-8"))
            doc_id = doc_dir.name
            doc_name = meta.get("file", doc_id)
            pages: List[Dict] = []
            for page_file in sorted(doc_dir.glob("page_*.json"), key=norm_page_order):
                pages.append(read_page_json(page_file))

            total_pages += len(pages)

            h1 = None
            h2 = None
            buffer: List[PageEntry] = []

            def flush_buffer() -> None:
                nonlocal buffer, total_chunks
                if not buffer:
                    return

                combined_parts: List[str] = []
                intervals: List[Tuple[int, int, int]] = []
                cursor = 0
                for entry in buffer:
                    if combined_parts:
                        combined_parts.append("\n")
                        cursor += 1
                    start = cursor
                    combined_parts.append(entry.text)
                    cursor += len(entry.text)
                    end = cursor
                    intervals.append((entry.page_no, start, end))

                combined_text = "".join(combined_parts).strip()
                if len(combined_text) < min_para_chars:
                    buffer.clear()
                    return

                segments = chunk_text(combined_text, max_chars, overlap_chars)
                for index, (segment_text, seg_start, seg_end) in enumerate(segments):
                    if len(segment_text.strip()) < min_para_chars:
                        continue
                    cover = pages_for_segment(intervals, seg_start, seg_end)
                    if not cover:
                        continue
                    span = [min(cover), max(cover)]
                    chunk_id = hash_id(doc_id, str(span[0]), str(span[1]), str(index), segment_text[:32])
                    record = {
                        "chunk_id": chunk_id,
                        "doc_id": doc_id,
                        "doc_name": doc_name,
                        "page_span": span,
                        "section_path": [sect for sect in [h1, h2] if sect],
                        "text": segment_text,
                    }
                    writer.write(json.dumps(record, ensure_ascii=False) + "\n")
                    total_chunks += 1
                    for page in cover:
                        pages_with_chunks.add((doc_id, page))
                buffer.clear()

            for page in pages:
                page_no = page.get("page_no")
                sections = build_sections(page.get("blocks", []))
                page_text = clean_page_text(page.get("text", ""))

                for is_heading, heading_text, font_size in sections:
                    if not is_heading:
                        continue
                    flush_buffer()
                    if font_size >= 18 or len(heading_text) <= 20:
                        h1, h2 = heading_text, None
                    else:
                        if not h1:
                            h1 = heading_text
                            h2 = None
                        else:
                            h2 = heading_text

                if page_text:
                    if not cross_page_merge and buffer:
                        flush_buffer()
                    buffer.append(PageEntry(page_no=page_no, text=page_text))
                    if not cross_page_merge:
                        flush_buffer()

            flush_buffer()

    coverage = len(pages_with_chunks) / max(total_pages, 1)
    quality = {
        "total_pages": total_pages,
        "total_chunks": total_chunks,
        "pages_with_chunks": len(pages_with_chunks),
        "page_coverage_ratio": round(coverage, 4),
        "params": {
            "max_chars": max_chars,
            "overlap_chars": overlap_chars,
            "min_paragraph_chars": min_para_chars,
            "cross_page_merge": cross_page_merge,
        },
    }
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "chunk_quality_from_chunker.json").write_text(
        json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(quality, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
