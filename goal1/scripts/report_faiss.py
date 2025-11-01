"""Generate Markdown leaderboard from FAISS evaluation outputs."""

from __future__ import annotations

import glob
import json
from pathlib import Path


def load_all() -> list[dict]:
    rows = []
    for path in glob.glob("results/faiss/*/metrics.json"):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        alias = data["alias"]
        doc_all = data["doc"]["all"]
        pas_all = data["passage"]["all"]
        rows.append(
            {
                "alias": alias,
                "Doc R@5": doc_all["R@5"],
                "Doc R@10": doc_all["R@10"],
                "Doc R@20": doc_all["R@20"],
                "Doc MRR@10": doc_all["MRR@10"],
                "Doc nDCG@10": doc_all["nDCG@10"],
                "Pass R@10": pas_all["R@10"],
                "Pass MRR@10": pas_all["MRR@10"],
                "Pass nDCG@10": pas_all["nDCG@10"],
            }
        )
    return rows


def fmt_row(row: dict) -> str:
    return (
        "| {alias} | {Doc R@5:.3f} | {Doc R@10:.3f} | {Doc R@20:.3f} | "
        "{Pass R@10:.3f} | {Doc MRR@10:.3f} | {Doc nDCG@10:.3f} |"
    ).format(**row)


def main() -> None:
    rows = load_all()
    rows.sort(key=lambda r: (r["Doc R@10"], r["Pass R@10"]), reverse=True)

    lines = [
        "# Embedding Leaderboard (FAISS)",
        "",
        "| Alias | Doc R@5 | Doc R@10 | Doc R@20 | Pass R@10 | Doc MRR@10 | Doc nDCG@10 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(fmt_row(row))

    out_path = Path("reports/embedding_leaderboard.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

