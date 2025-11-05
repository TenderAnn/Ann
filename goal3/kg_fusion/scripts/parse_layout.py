"""PDF layout parsing with multi-column ordering and slicing fixes."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import List, Dict, Any

import fitz  # PyMuPDF
import numpy as np
from kg_fusion.paths import data_path

RE_HEADING_PAT = re.compile(
    r"^((第[一二三四五六七八九十百]+[章节])|([一二三四五六七八九十]+、)|(（[一二三四五六七八九十]+）)|([0-9]{1,2}[.、]))"
)
RE_PUNCT_END = re.compile(r"[。；;！？!?…)]$")


def looks_like_heading(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if RE_HEADING_PAT.match(stripped):
        return True
    lowered = stripped.lower()
    return lowered.startswith(("chapter", "section", "appendix"))


def norm_text(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\t", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("保 费", "保费").replace("年 金", "年金")
    text = re.sub(r"(\d+)\s*年\s*内", r"\1年内", text)
    return text


def detect_columns(lines: List[Dict[str, Any]], page_width: float) -> tuple[int, tuple[float, float] | None]:
    xs = np.array([ln["x_center"] for ln in lines if ln["text"].strip()])
    if len(xs) < 40:
        return 1, None
    mid = page_width / 2
    margin = page_width * 0.08
    left = (xs < mid - margin).sum()
    right = (xs > mid + margin).sum()
    if left > 0.2 * len(xs) and right > 0.2 * len(xs):
        return 2, (mid, margin)
    return 1, None


def merge_lines_to_paras(lines: List[Dict[str, Any]], gap_factor: float = 1.2) -> List[Dict[str, Any]]:
    paragraphs: List[List[Dict[str, Any]]] = []
    buffer: List[Dict[str, Any]] = []
    last_line: Dict[str, Any] | None = None

    for line in lines:
        text = line["text"].strip()
        if not text:
            continue
        current_heading = looks_like_heading(text)
        if last_line is None:
            buffer = [line]
        else:
            if current_heading and buffer:
                paragraphs.append(buffer)
                buffer = [line]
                last_line = line
                continue
            gap = line["y0"] - last_line["y1"]
            avg_size = (line["avg_size"] + last_line["avg_size"]) / 2 or 10
            threshold = gap_factor * avg_size
            prev_text = last_line["text"].strip()
            heading_like = looks_like_heading(prev_text)
            join_hint = (not RE_PUNCT_END.search(prev_text) or prev_text.endswith(("-", "‐", "—", "~"))) and not heading_like
            if gap < threshold or join_hint:
                buffer.append(line)
            else:
                paragraphs.append(buffer)
                buffer = [line]
        last_line = line
    if buffer:
        paragraphs.append(buffer)

    merged: List[Dict[str, Any]] = []
    for seg in paragraphs:
        text = " ".join(s["text"].rstrip("-‐—~") for s in seg)
        text = text.replace("- ", "").replace("‐ ", "").replace("— ", "").replace("~ ", "")
        text = norm_text(text)
        x0 = min(s["bbox"][0] for s in seg)
        y0 = min(s["bbox"][1] for s in seg)
        x1 = max(s["bbox"][2] for s in seg)
        y1 = max(s["bbox"][3] for s in seg)
        merged.append(
            {
                "text": text,
                "bbox": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                "y0": y0,
                "y1": y1,
                "avg_size": float(np.mean([s["avg_size"] for s in seg])),
            }
        )
    return merged


def page_to_lines(page) -> List[Dict[str, Any]]:
    data = page.get_text("dict")
    lines: List[Dict[str, Any]] = []
    for block in data.get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text = "".join(span.get("text", "") for span in spans)
            if not text.strip():
                continue
            sizes = [span.get("size", 10) for span in spans]
            x0 = min(span.get("bbox", [0, 0, 0, 0])[0] for span in spans)
            y0 = min(span.get("bbox", [0, 0, 0, 0])[1] for span in spans)
            x1 = max(span.get("bbox", [0, 0, 0, 0])[2] for span in spans)
            y1 = max(span.get("bbox", [0, 0, 0, 0])[3] for span in spans)
            lines.append(
                {
                    "text": text,
                    "bbox": [x0, y0, x1, y1],
                    "y0": y0,
                    "y1": y1,
                    "avg_size": float(np.mean(sizes)),
                    "x_center": (x0 + x1) / 2,
                }
            )
    return lines


def split_columns(lines: List[Dict[str, Any]], page_width: float) -> List[List[Dict[str, Any]]]:
    if not lines:
        return [lines]
    cols, gate = detect_columns(lines, page_width)
    if cols == 1 or gate is None:
        return [sorted(lines, key=lambda ln: (ln["y0"], ln["bbox"][0]))]
    mid, margin = gate
    left = [ln for ln in lines if ln["x_center"] < mid - margin]
    right = [ln for ln in lines if ln["x_center"] > mid + margin]
    left.sort(key=lambda ln: (ln["y0"], ln["bbox"][0]))
    right.sort(key=lambda ln: (ln["y0"], ln["bbox"][0]))
    return [left, right]


def is_heading(text: str, avg_size: float, size_threshold: float) -> tuple[bool, int]:
    stripped = text.strip()
    lowered = stripped.lower()
    if avg_size >= size_threshold:
        return True, 1
    if lowered.startswith("chapter"):
        return True, 1
    if lowered.startswith(("section", "appendix")):
        return True, 2
    if RE_HEADING_PAT.match(stripped):
        return True, 2
    return False, 0


def build_sections(pdf_path: Path, out_path: Path) -> None:
    doc = fitz.open(pdf_path)
    doc_id = pdf_path.stem

    sizes: List[float] = []
    for page in doc:
        data = page.get_text("dict")
        for block in data.get("blocks", []):
            if block.get("type", 0) != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    sizes.append(span.get("size", 10))
    if sizes:
        percentile = float(np.percentile(sizes, 85))
        median = float(np.median(sizes))
        size_threshold = max(percentile, median + 1.0)
    else:
        size_threshold = 14.0

    heading_stack: List[tuple[int, str]] = []
    section_idx = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as fp:
        for page_no, page in enumerate(doc, start=1):
            page_width = page.rect.width
            lines = page_to_lines(page)
            col_lines = split_columns(lines, page_width)
            ordered_lines = col_lines[0] if len(col_lines) == 1 else col_lines[0] + col_lines[1]
            paragraphs = merge_lines_to_paras(ordered_lines)

            for para in paragraphs:
                text = para["text"].strip()
                if not text:
                    continue
                heading_flag, level = is_heading(text, para["avg_size"], size_threshold)
                if heading_flag:
                    while heading_stack and heading_stack[-1][0] >= level and level > 0:
                        heading_stack.pop()
                    heading_stack.append((level or 1, text))
                heading_path = " > ".join(h[1] for h in heading_stack)

                record = {
                    "doc_id": doc_id,
                    "page_no": page_no,
                    "section_id": f"{doc_id}-{section_idx:05d}",
                    "bbox": para["bbox"],
                    "is_heading": heading_flag,
                    "heading_level": level,
                    "heading_path": heading_path,
                    "text": text,
                }
                section_idx += 1
                fp.write(json.dumps(record, ensure_ascii=False) + "\n")

    doc.close()


def parse_batch(in_dir: Path, out_dir: Path) -> None:
    pdfs = sorted(in_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs under {in_dir}")
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    for pdf in pdfs:
        out_file = out_dir / f"{pdf.stem}.sections.jsonl"
        print(f"Parsing {pdf.name} -> {out_file.name}")
        build_sections(pdf, out_file)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in_dir", default=str(data_path("raw")))
    parser.add_argument("--out_dir", default=str(data_path("parsed")))
    args = parser.parse_args()

    parse_batch(Path(args.in_dir), Path(args.out_dir))


if __name__ == "__main__":
    main()
