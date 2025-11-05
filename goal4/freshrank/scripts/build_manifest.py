"""Generate a manifest snapshot for configs."""
from __future__ import annotations

from pathlib import Path

from freshrank.service.pipeline import RankingPipeline


def main() -> None:
    pipeline = RankingPipeline()
    target = Path("data/metadata/manifest.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    pipeline.dump_manifest(target)
    print(f"Manifest written to {target}")


if __name__ == "__main__":
    main()
