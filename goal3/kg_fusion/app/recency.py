"""Recency metadata loading and scoring utilities."""
from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Tuple

from ..paths import data_path, env_or_path

RECENCY_CSV = env_or_path("RECENCY_CSV", data_path("kg", "recency_meta.csv"))


def load_recency() -> Dict[str, Dict[str, str]]:
    path = Path(RECENCY_CSV)
    if not path.exists():
        return {}
    data: Dict[str, Dict[str, str]] = {}
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            data[row["doc_id"]] = {
                "effective_date": (row.get("effective_date") or "").strip(),
                "discontinue_date": (row.get("discontinue_date") or "").strip(),
            }
    return data


def _parse(date_str: str) -> date | None:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None


def recency_score(meta: Dict[str, str]) -> Tuple[float, Dict[str, bool]]:
    """Return bonus/penalty score and flags based on recency."""
    today = date.today()
    bonus = 0.0
    flags: Dict[str, bool] = {}
    eff = _parse(meta.get("effective_date", ""))
    dis = _parse(meta.get("discontinue_date", ""))
    if eff:
        diff = (today - eff).days
        if diff <= 180:
            bonus += 0.3
            flags["fresh"] = True
    if dis:
        if (today - dis).days >= 0:
            bonus -= 0.4
            flags["outdated"] = True
    return bonus, flags
