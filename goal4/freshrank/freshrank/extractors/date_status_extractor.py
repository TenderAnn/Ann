"""Utilities to derive effective/expiry metadata from sales corpus."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import re

import dateparser


@dataclass
class DocumentTemporalMetadata:
    effective_date: Optional[datetime]
    expiry_date: Optional[datetime]
    collected_at: datetime

    @property
    def is_expired(self) -> bool:
        if self.expiry_date is None:
            return False
        return self.expiry_date < self.collected_at


def parse_temporal_fields(text: str, *, collected_at: Optional[datetime] = None) -> DocumentTemporalMetadata:
    """Parse free text for effective/expiry markers with a deterministic default."""
    collected_at = collected_at or datetime.now(timezone.utc)
    effective = _search_date(text, ["生效", "发布", "适用"])
    expiry = _search_date(text, ["截止", "废止", "终止"])
    return DocumentTemporalMetadata(effective_date=effective, expiry_date=expiry, collected_at=collected_at)


DATE_PATTERN = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")


def _search_date(text: str, anchors: list[str]) -> Optional[datetime]:
    for token in anchors:
        idx = text.find(token)
        if idx == -1:
            continue
        window = text[idx : idx + 32]
        match = DATE_PATTERN.search(window)
        if match:
            year, month, day = map(int, match.groups())
            return datetime(year, month, day)
        parsed = dateparser.parse(window, languages=["zh"])
        if parsed:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
    return None
