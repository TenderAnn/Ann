"""Parse tables extracted from PDFs to normalized rows."""
from __future__ import annotations

from typing import Iterable, List


def normalize_table(rows: Iterable[Iterable[str]]) -> List[dict]:
    rows = list(rows)
    if not rows:
        return []
    header = [cell.strip().lower() for cell in rows[0]]
    normalized = []
    for row in rows[1:]:
        normalized.append({header[i]: cell.strip() for i, cell in enumerate(row) if i < len(header)})
    return normalized
