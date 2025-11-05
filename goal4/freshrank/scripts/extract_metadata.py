"""Extract temporal and regulatory metadata from parsed corpus."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import dateparser

DATE_FIELDS = {
    "publish_date": [r"发布日期[:：]\s*(20\d{2}年\d{1,2}月\d{1,2}日)"],
    "effective_from": [r"生效日期[:：]\s*(20\d{2}年\d{1,2}月\d{1,2}日)"],
    "effective_to": [r"(废止|终止|截止)日期[:：]?\s*(20\d{2}年\d{1,2}月\d{1,2}日)"],
}
STATUS_PATTERNS = [
    ("已废止", "expired"),
    ("停售", "discontinued"),
    ("在售", "active"),
]
VERSION_PATTERN = re.compile(r"版本[:：]?\s*([A-Za-z0-9.]+)")
PRODUCT_PATTERN = re.compile(r"产品代码[:：]?\s*([A-Z]{2,}\d+)")


def load_doc_types(path: Path) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not path.exists():
        return mapping
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            mapping[payload.get("doc_id")] = payload.get("doc_type")
    return mapping


def parse_date(value: str) -> Optional[str]:
    parsed = dateparser.parse(value, languages=["zh"], settings={"TIMEZONE": "UTC", "RETURN_AS_TIMEZONE_AWARE": True})
    if not parsed:
        return None
    return parsed.astimezone(timezone.utc).isoformat()


def extract_field(patterns: List[str], text: str) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(match.lastindex or 1)
    return None


def detect_status(text: str) -> str:
    for keyword, status in STATUS_PATTERNS:
        if keyword in text:
            return status
    return "active"


def extract_metadata(doc_path: Path, doc_type: Optional[str]) -> dict:
    text = doc_path.read_text(encoding="utf-8")
    data = {
        "doc_id": doc_path.stem,
        "doc_type": doc_type,
        "publish_date": None,
        "effective_from": None,
        "effective_to": None,
        "status": detect_status(text),
        "version": None,
        "product_code": None,
    }
    for field, patterns in DATE_FIELDS.items():
        raw = extract_field(patterns, text)
        if raw:
            data[field] = parse_date(raw)
    version = VERSION_PATTERN.search(text)
    if version:
        data["version"] = version.group(1)
    product = PRODUCT_PATTERN.search(text)
    if product:
        data["product_code"] = product.group(1)
    expiry = data.get("effective_to")
    if expiry:
        data["expired"] = datetime.fromisoformat(expiry).astimezone(timezone.utc) < datetime.now(timezone.utc)
    else:
        data["expired"] = False
    filled = sum(1 for key in ("publish_date", "effective_from", "effective_to") if data.get(key))
    data["extraction_confidence"] = round(0.6 + 0.1 * filled, 2)
    return data


def run(args: argparse.Namespace) -> None:
    doc_types = load_doc_types(Path(args.doc_types))
    input_path = Path(args.input)
    rows: List[dict] = []
    for path in sorted(input_path.glob("*.txt")):
        rows.append(extract_metadata(path, doc_types.get(path.stem)))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Saved {len(rows)} metadata rows to {args.out}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract document metadata")
    parser.add_argument("--input", default="data/parsed")
    parser.add_argument("--doc-types", default="data/metadata/doc_types.jsonl")
    parser.add_argument("--out", default="data/metadata/metadata.jsonl")
    return parser.parse_args()


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
