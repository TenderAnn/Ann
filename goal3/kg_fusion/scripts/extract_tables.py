"""Extract tables with coordinates from PDFs using pdfplumber."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List

import pdfplumber

from kg_fusion.app.table_aliases import to_canonical
from kg_fusion.paths import data_path

TABLE_SETTINGS = dict(
    vertical_strategy="lines",
    horizontal_strategy="lines",
    intersection_tolerance=5,
    snap_tolerance=3,
    join_tolerance=3,
    edge_min_length=3,
    min_words_horizontal=1,
)


@dataclass
class Cell:
    row: int
    col: int
    text: str
    bbox: List[float]


@dataclass
class TableRecord:
    doc_id: str
    table_id: str
    page_no: int
    bbox: List[float]
    n_rows: int
    n_cols: int
    header_rows: List[int]
    header_map: Dict[int, str]
    cells: List[Cell]


def safe_stem(path: Path) -> str:
    return path.stem.replace(" ", "_")


def is_mostly_numeric(text: str) -> bool:
    if not text:
        return False
    stripped = text.replace("%", "").replace("‰", "").replace(",", "")
    stripped = stripped.replace("，", "").strip()
    return stripped.isdigit()


def guess_header_rows(rows: List[List[str]]) -> List[int]:
    if not rows:
        return []
    first = rows[0]
    if first:
        non_numeric = sum(1 for cell in first if cell and not is_mostly_numeric(cell))
        if len(first) and non_numeric / len(first) >= 0.6:
            return [0]
    if len(rows) > 1:
        second = rows[1]
        non_numeric2 = sum(1 for cell in second if cell and not is_mostly_numeric(cell))
        if len(second) and non_numeric2 / len(second) >= 0.6:
            return [1]
    return [0]


def build_header_map(header_row: List[str]) -> Dict[int, str]:
    mapping: Dict[int, str] = {}
    for idx, header in enumerate(header_row or []):
        mapping[idx] = to_canonical(header or "")
    return mapping


def extract_pdf(pdf_path: Path, out_path: Path) -> None:
    doc_id = safe_stem(pdf_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    table_counter = 0

    with pdfplumber.open(pdf_path) as pdf, out_path.open("w", encoding="utf-8") as fh:
        for page_no, page in enumerate(pdf.pages, start=1):
            try:
                tables = page.find_tables(table_settings=TABLE_SETTINGS)
            except Exception:
                tables = []
            for table in tables:
                table_counter += 1
                table_id = f"{doc_id}-t{table_counter:04d}"
                raw_rows = table.extract() or []
                header_rows = guess_header_rows(raw_rows)
                header_row_idx = header_rows[0] if header_rows and len(raw_rows) > header_rows[0] else None
                header_map = build_header_map(raw_rows[header_row_idx]) if header_row_idx is not None else {}

                cells: List[Cell] = []
                n_rows = len(raw_rows)
                n_cols = max((len(row) for row in raw_rows), default=0)
                for r_idx, row_values in enumerate(raw_rows):
                    for c_idx, value in enumerate(row_values):
                        if r_idx < len(table.rows) and c_idx < len(table.rows[r_idx].cells):
                            x0, top, x1, bottom = table.rows[r_idx].cells[c_idx]
                        else:
                            x0, top, x1, bottom = table.bbox
                        cells.append(
                            Cell(
                                row=r_idx,
                                col=c_idx,
                                text=(value or "").strip(),
                                bbox=[round(float(x0), 2), round(float(top), 2), round(float(x1), 2), round(float(bottom), 2)],
                            )
                        )

                record = TableRecord(
                    doc_id=doc_id,
                    table_id=table_id,
                    page_no=page_no,
                    bbox=[round(float(table.bbox[0]), 2), round(float(table.bbox[1]), 2),
                          round(float(table.bbox[2]), 2), round(float(table.bbox[3]), 2)],
                    n_rows=n_rows,
                    n_cols=n_cols,
                    header_rows=header_rows,
                    header_map=header_map,
                    cells=cells,
                )
                fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in_dir", default=str(data_path("raw")))
    parser.add_argument("--out_dir", default=str(data_path("tables")))
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(in_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {in_dir}")
        return
    for pdf in pdfs:
        out_file = out_dir / f"{pdf.stem}.tables.jsonl"
        print(f"Extracting tables: {pdf.name} -> {out_file.name}")
        extract_pdf(pdf, out_file)


if __name__ == "__main__":
    main()
