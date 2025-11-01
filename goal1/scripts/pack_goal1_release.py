"""Package goal1 reproducible bundle as a zip archive."""

from __future__ import annotations

import argparse
import json
import os
import random
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable, List


ROOT = Path(".")
DEFAULT_FILES = [
    "requirements.txt",
    "README.md",
    "technical_route.md",
    "final_project_framework.md",
    "reports/embedding_leaderboard.md",
    "reports/embedding_eval_report.md",
]


def add_file(zipf: zipfile.ZipFile, path: Path, arc_root: Path) -> None:
    arcname = arc_root / path.relative_to(ROOT)
    zipf.write(path, arcname.as_posix())


def collect_directories() -> List[str]:
    dirs = []
    for name in ["scripts", "configs", "artifacts", "testsuite"]:
        path = ROOT / name
        if path.exists():
            dirs.append(name)
    return dirs


def sample_topk_files(directory: Path, limit: int = 10) -> List[Path]:
    files = sorted(directory.glob("Q*.json"))
    if len(files) <= limit:
        return files
    random.seed(42)
    return random.sample(files, limit)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None, help="输出 zip 路径（默认 release/goal1_v1.zip）")
    parser.add_argument("--include-indexes", action="store_true", help="是否包含 indexes/*.parquet（体积较大）")
    parser.add_argument("--include-topk", action="store_true", help="是否包含 topk 样例（默认抽样 10 条）")
    args = parser.parse_args()

    output_path = Path(args.out) if args.out else Path("release") / "goal1_v1.zip"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        arc_root = Path("goal1")

        for dirname in collect_directories():
            for path in (ROOT / dirname).rglob("*"):
                if path.is_file():
                    add_file(zipf, path, arc_root)

        patterns = [
            "results/faiss/*/metrics.json",
            "results/hybrid/*/metrics.json",
            "results/rerank/*/metrics.json",
        ]
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                add_file(zipf, path, arc_root)

        if args.include_topk:
            for base_dir in ["results/faiss", "results/hybrid", "results/rerank"]:
                root_dir = ROOT / base_dir
                if not root_dir.exists():
                    continue
                for alias_dir in root_dir.glob("*"):
                    topk_dir = alias_dir / "topk"
                    if not topk_dir.exists():
                        continue
                    for sample in sample_topk_files(topk_dir, limit=10):
                        add_file(zipf, sample, arc_root)

        for file_name in DEFAULT_FILES:
            path = ROOT / file_name
            if path.exists():
                add_file(zipf, path, arc_root)

        if not (ROOT / "README.md").exists():
            readme = """# 目标一 可复现测试包（Goal1 Release）

## 快速开始
1) 安装依赖：`python -m pip install -r requirements.txt`
2) 可选：设置聚合网关（bianxie.ai）或 OpenAI：
   - `export BIANXIE_API_KEY=...`
   - `export OPENAI_BASE_URL=https://api.bianxie.ai/v1`  # 切回官方则 https://api.openai.com/v1
3) 复现实验（示例）：
   - `python scripts/eval_faiss.py --alias bge_large_zh_v1_5_mean_cos --topk 100 --qrels-doc testsuite/qrels_doc_multi.tsv`
   - `python scripts/bm25_and_fusion_eval.py --alias bge_large_zh_v1_5_mean_cos`
   - `python scripts/rerank_cross_encoder.py --alias bge_large_zh_v1_5_mean_cos --topk-dir results/hybrid/bge_large_zh_v1_5_mean_cos/topk`
   - `python scripts/eval_topk_from_json.py --topk-dir results/rerank/bge_large_zh_v1_5_mean_cos/topk --qrels-doc testsuite/qrels_doc_multi.tsv`
4) 文档：
   - `reports/embedding_leaderboard.md`
   - `reports/embedding_eval_report.md`
   - `technical_route.md`（技术路线与复现）
   - `final_project_framework.md`（框架与结论）
"""
            temp_readme = ROOT / "README.release.md"
            temp_readme.write_text(readme, encoding="utf-8")
            add_file(zipf, temp_readme, arc_root / "README.md")
            temp_readme.unlink(missing_ok=True)

        if args.include_indexes:
            for parquet_path in ROOT.glob("indexes/*/*.parquet"):
                add_file(zipf, parquet_path, arc_root)

        meta = {
            "created_at": datetime.utcnow().isoformat() + "Z",
            "host": os.uname().sysname if hasattr(os, "uname") else "unknown",
            "notes": "Goal1 reproducible package; metrics only, indexes optional.",
        }
        meta_path = ROOT / "release_meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        add_file(zipf, meta_path, arc_root)
        meta_path.unlink(missing_ok=True)

    print(f"Packed -> {output_path}")


if __name__ == "__main__":
    main()
