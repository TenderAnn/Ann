"""Generate SHA256 fingerprints for critical configuration files."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

CONFIG_ORDER = [
    Path("regulatory/rulebook.yaml"),
    Path("regulatory/taxonomy.yaml"),
    Path("regulatory/weights.yaml"),
]
LEXICON_DIR = Path("regulatory/lexicon")
CONFIG_ORDER.extend(sorted(LEXICON_DIR.glob("*.txt")))
CONFIG_ORDER.append(Path("freshrank/config/ranking_rules.yaml"))


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def main() -> None:
    records = []
    combined_stream = hashlib.sha256()
    for cfg in CONFIG_ORDER:
        if not cfg.exists():
            raise SystemExit(f"Missing config file: {cfg}")
        digest = sha256_file(cfg)
        records.append({"path": str(cfg), "sha256": digest})
        combined_stream.update(digest.encode("utf-8"))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": records,
        "combined_hash": combined_stream.hexdigest(),
    }
    out_path = Path("eval/reports/config_fingerprint.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Config fingerprint saved to {out_path}")


if __name__ == "__main__":
    main()
