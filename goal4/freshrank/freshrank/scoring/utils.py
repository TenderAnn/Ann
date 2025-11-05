"""Shared helpers for scoring."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional


def days_since(value: Optional[datetime]) -> Optional[int]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return max(0, (now - value).days)


def find_tier(tiers: Iterable[dict], age_days: Optional[int], expired: bool) -> dict:
    if expired:
        return next((tier for tier in tiers if tier.get("id") == "stale"), {"multiplier": 0.5})
    if age_days is None:
        return next((tier for tier in tiers if tier.get("id") == "active_baseline"), {"multiplier": 1.0})
    for tier in tiers:
        max_age = tier.get("max_age_days")
        if max_age is None or age_days <= max_age:
            return tier
    return tiers[-1] if tiers else {"multiplier": 1.0}
