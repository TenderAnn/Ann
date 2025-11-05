"""Extract effective/expiry dates from parsed sections into recency metadata."""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Iterable, Tuple

from dateutil import parser as dparser
from kg_fusion.paths import data_path

RE_DATE_PATTERNS = [
    # 生效/实施
    (r"(生效|实施|起始|effective\s*date|valid\s*from)\D{0,8}([0-9]{4}[./-][0-9]{1,2}[./-][0-9]{1,2})", "E1"),
    (r"(生效|实施|起始)\D{0,8}([0-9]{4})年([0-9]{1,2})月([0-9]{1,2})日", "E2"),
    # 废止/停售
    (r"(废止|终止|停售|失效|discontinue|expire[sd]?)\D{0,8}([0-9]{4}[./-][0-9]{1,2}[./-][0-9]{1,2})", "D1"),
    (r"(废止|终止|停售|失效)\D{0,8}([0-9]{4})年([0-9]{1,2})月([0-9]{1,2})日", "D2"),
]


def _norm_date(raw: str) -> str | None:
    try:
        dt = dparser.parse(raw, fuzzy=True, dayfirst=False, yearfirst=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def _scan(text: str) -> Tuple[str | None, str | None, list[tuple[str, str, str]]]:
    eff = None
    dis = None
    hits: list[tuple[str, str, str]] = []
    hay = text or ""
    for pattern, code in RE_DATE_PATTERNS:
        for match in re.finditer(pattern, hay, flags=re.IGNORECASE):
            date_text = match.group(0)
            if code in {"E2", "D2"}:
                y, m, d = match.group(2), match.group(3), match.group(4)
                date_text = f"{y}-{m}-{d}"
            normalized = _norm_date(date_text)
            if not normalized:
                continue
            if code.startswith("E") and not eff:
                eff = normalized
                hits.append(("effective_date", normalized, code))
            if code.startswith("D") and not dis:
                dis = normalized
                hits.append(("discontinue_date", normalized, code))
            if eff and dis:
                break
        if eff and dis:
            break
    return eff, dis, hits


def _iter_sections(path: Path) -> Iterable[dict]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def main(parsed_dir: str, out_csv: str) -> None:
    parsed_path = Path(parsed_dir)
    out_path = Path(out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    for sections_file in parsed_path.glob("*.sections.jsonl"):
        doc_id = sections_file.stem.replace(".sections", "")
        eff = None
        dis = None
        sources: list[tuple[str, str, str, str]] = []
        for sec in _iter_sections(sections_file):
            snippet = f"{sec.get('heading_path','')} {sec.get('text','')}".strip()
            found_eff, found_dis, hits = _scan(snippet)
            eff = eff or found_eff
            dis = dis or found_dis
            for field, value, code in hits:
                sources.append((sec.get("section_id", ""), field, value, code))
            if eff and dis:
                break
        records.append(
            {
                "doc_id": doc_id,
                "effective_date": eff or "",
                "discontinue_date": dis or "",
                "sources": json.dumps(sources, ensure_ascii=False),
            }
        )

    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["doc_id", "effective_date", "discontinue_date", "sources"])
        writer.writeheader()
        writer.writerows(records)
    print(f"Wrote {out_path} ({len(records)} docs)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--parsed_dir", default=str(data_path("parsed")))
    parser.add_argument("--out_csv", default=str(data_path("kg", "recency_meta.csv")))
    args = parser.parse_args()
    main(args.parsed_dir, args.out_csv)
