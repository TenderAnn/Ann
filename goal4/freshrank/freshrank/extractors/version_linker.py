"""Link document versions via metadata fingerprints."""
from __future__ import annotations

import hashlib
from typing import Dict, Iterable


def fingerprint(record: Dict[str, str]) -> str:
    payload = "|".join(f"{k}:{record.get(k,'')}" for k in sorted(record))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def link_versions(records: Iterable[Dict[str, str]]) -> Dict[str, list[str]]:
    buckets: Dict[str, list[str]] = {}
    for rec in records:
        fp = fingerprint(rec)
        buckets.setdefault(fp[:12], []).append(rec.get("doc_id", "unknown"))
    return buckets
