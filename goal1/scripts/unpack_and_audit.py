"""Data unpacking and corpus health audit utilities."""

import argparse
import json
import math
import os
import random
import statistics
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from loguru import logger

import fitz  # type: ignore


RANDOM_SEED = 42
READABLE_PUNCT = set("，。；：！？、（）()[]{}《》<>“”‘’.-_/\\:;!?,'\"&%+@#*^=~`|·…")


def is_cjk(ch: str) -> bool:
    code = ord(ch)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0x20000 <= code <= 0x2A6DF
        or 0x2A700 <= code <= 0x2B73F
        or 0x2B740 <= code <= 0x2B81F
        or 0x2B820 <= code <= 0x2CEAF
        or 0xF900 <= code <= 0xFAFF
    )


def is_readable_char(ch: str) -> bool:
    return ch.isascii() and (ch.isalnum() or ch.isspace()) or is_cjk(ch) or ch in READABLE_PUNCT


def safe_extract_zip(zip_path: Path, dest_dir: Path) -> List[Path]:
    extracted: List[Path] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            name = member.filename
            if name.endswith("/") or "__MACOSX" in name:
                continue
            if not name.lower().endswith(".pdf"):
                continue
            target = dest_dir / Path(name).name
            target_parent = target.parent.resolve()
            dest_resolved = dest_dir.resolve()
            if not str(target_parent).startswith(str(dest_resolved)):
                logger.warning(f"Skip suspicious path: {name}")
                continue
            with zf.open(member) as src, open(target, "wb") as out:
                out.write(src.read())
            extracted.append(target)
    return extracted


def find_pdfs(raw_dir: Path) -> List[Path]:
    return sorted([p for p in raw_dir.rglob("*.pdf") if p.is_file()])


def page_count(pdf_path: Path) -> int:
    try:
        with fitz.open(pdf_path) as doc:
            return doc.page_count
    except Exception as exc:
        logger.warning(f"Cannot open {pdf_path}: {exc}")
        return 0


def doc_readability(pdf_path: Path, max_pages: int = 8) -> float:
    try:
        with fitz.open(pdf_path) as doc:
            n = min(max_pages, doc.page_count)
            if n == 0:
                return 0.0
            ratios: List[float] = []
            for index in range(n):
                try:
                    page = doc.load_page(index)
                    text = page.get_text("text") or ""
                    if not text:
                        ratios.append(0.0)
                        continue
                    total = len(text)
                    good = sum(1 for ch in text if is_readable_char(ch))
                    ratios.append(good / max(total, 1))
                except Exception as page_exc:
                    logger.debug(f"Readability error {pdf_path} p{index}: {page_exc}")
                    ratios.append(0.0)
            return float(sum(ratios) / len(ratios))
    except Exception as exc:
        logger.warning(f"Open error for readability {pdf_path}: {exc}")
        return 0.0


def quantiles(values: List[float]) -> Dict[str, float]:
    if not values:
        return {k: 0.0 for k in ["p10", "p25", "p50", "p75", "p90"]}
    values_sorted = sorted(values)

    def q(p: float) -> float:
        idx = (len(values_sorted) - 1) * p
        lo, hi = math.floor(idx), math.ceil(idx)
        if lo == hi:
            return float(values_sorted[int(idx)])
        frac = idx - lo
        return float(values_sorted[lo] * (1 - frac) + values_sorted[hi] * frac)

    return {
        "p10": q(0.10),
        "p25": q(0.25),
        "p50": q(0.50),
        "p75": q(0.75),
        "p90": q(0.90),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=str, default=None, help="Path to shuju.zip (optional)")
    parser.add_argument("--raw-dir", type=str, default="data/raw", help="Raw PDF root")
    parser.add_argument("--out", type=str, default="results/data_audit.json", help="Output JSON path")
    parser.add_argument("--sample", type=int, default=20, help="Sample PDF count for readability")
    parser.add_argument("--max-pages", type=int, default=8, help="Max pages per doc for readability")
    args = parser.parse_args()

    random.seed(RANDOM_SEED)
    raw_dir = Path(args.raw_dir)
    out_path = Path(args.out)
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.zip:
        zip_path = Path(args.zip)
        if not zip_path.exists():
            logger.error(f"Zip not found: {zip_path}")
            sys.exit(2)
        logger.info(f"Extracting PDFs from {zip_path} -> {raw_dir}")
        extracted = safe_extract_zip(zip_path, raw_dir)
        logger.info(f"Extracted {len(extracted)} PDFs")

    pdfs = find_pdfs(raw_dir)
    total = len(pdfs)
    logger.info(f"Found {total} PDFs under {raw_dir}")

    page_counts = [page_count(p) for p in pdfs]
    page_counts = [count for count in page_counts if count > 0]
    if page_counts:
        pcs: Dict[str, Any] = {
            "min": int(min(page_counts)),
            "max": int(max(page_counts)),
            "mean": float(sum(page_counts) / len(page_counts)),
            "median": float(statistics.median(page_counts)),
        }
    else:
        pcs = {"min": 0, "max": 0, "mean": 0.0, "median": 0.0}

    sample_n = min(args.sample, total)
    sample_paths = random.sample(pdfs, sample_n) if sample_n > 0 else []
    read_vals = [doc_readability(path, args.max_pages) for path in sample_paths]
    q_vals = quantiles(read_vals)

    ocr_recommended = (q_vals["p50"] < 0.70) or (q_vals["p90"] < 0.90)
    suggestion = {
        "ocr_recommended": ocr_recommended,
        "suggested_ocr_trigger_ratio": 0.10 if ocr_recommended else 0.0,
    }

    buckets: Dict[str, int] = {}
    for pdf in pdfs:
        try:
            rel = pdf.relative_to(raw_dir)
            top = rel.parts[0] if len(rel.parts) > 1 else "_root"
        except Exception:
            top = "_root"
        buckets[top] = buckets.get(top, 0) + 1

    report: Dict[str, Any] = {
        "raw_dir": str(raw_dir),
        "pdf_count": total,
        "page_stats": pcs,
        "readability_sample_size": sample_n,
        "readability_quantiles": q_vals,
        "ocr_decision": suggestion,
        "top_level_distribution": buckets,
        "sample_files": [str(path) for path in sample_paths],
        "parameters": {
            "max_pages_per_doc": args.max_pages,
            "random_seed": RANDOM_SEED,
        },
    }

    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    logger.info(f"Wrote audit to {out_path}")

    print("\n=== DATA AUDIT SUMMARY ===")
    print(
        f"Pages  min/median/mean/max: "
        f"{pcs['min']} / {pcs['median']} / {pcs['mean']:.2f} / {pcs['max']}"
    )
    print(f"PDFs: {total}")
    print(f"Readability p50={q_vals['p50']:.2f}, p90={q_vals['p90']:.2f}")
    print(
        f"OCR recommended: {ocr_recommended} "
        f"(trigger_ratio={suggestion['suggested_ocr_trigger_ratio']})"
    )
    print("Top-level folders (top 10):")
    for key, value in sorted(buckets.items(), key=lambda kv: kv[1], reverse=True)[:10]:
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()

