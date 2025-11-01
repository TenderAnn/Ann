"""Clean product names to canonical short forms."""

from __future__ import annotations

import json
import re
from pathlib import Path

PMAP_IN = Path("artifacts/product_name_map.json")
PMAP_OUT = Path("artifacts/product_name_map.clean.json")

COMPANY_PAT = re.compile(r"^(?:[\u4e00-\u9fa5A-Za-z0-9（）()·\s]*?公司\s*)+")
TRAIL_PAT = re.compile(r"(保险)?(条款|产品说明书|费率表|基本保险金额表)$")
BRACKET_PAT = re.compile(r"[《》]")


def clean_name(name: str) -> str:
    cleaned = BRACKET_PAT.sub("", name or "").strip()
    cleaned = COMPANY_PAT.sub("", cleaned)
    cleaned = re.sub(r"\s+", "", cleaned)
    cleaned = TRAIL_PAT.sub("", cleaned)
    cleaned = re.sub(r"(条款|说明书|费率表)$", "", cleaned)
    if len(cleaned) > 30:
        cleaned = cleaned[:30]
    return cleaned or name


def main() -> None:
    raw_map = json.loads(PMAP_IN.read_text(encoding="utf-8"))
    base_to_name: dict[str, str] = {}
    for doc_id, value in raw_map.items():
        base = doc_id.split("__")[0]
        candidate = clean_name(value or base)
        if base not in base_to_name or len(candidate) < len(base_to_name[base]):
            base_to_name[base] = candidate

    output: dict[str, str] = {}
    for doc_id, value in raw_map.items():
        base = doc_id.split("__")[0]
        output[doc_id] = base_to_name.get(base, clean_name(value or base))

    PMAP_OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"cleaned": len(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
