"""Build evaluation queries and qrels from chunked corpus."""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import yaml


def load_yaml(path: Path) -> Dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_chunks(path: Path) -> Iterable[Dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def norm_prod_name(doc_id: str, doc_name: Optional[str]) -> str:
    base = doc_name or doc_id
    base = re.sub(r"__.*$", "", base)
    return base


def guess_product_name(doc_chunks: List[Dict], name_patterns: List[str]) -> Optional[str]:
    front = sorted(
        doc_chunks,
        key=lambda ch: (ch.get("page_span", [0, 0])[0], ch.get("page_span", [0, 0])[1]),
    )[:8]
    for pattern in name_patterns:
        regex = re.compile(pattern)
        for chunk in front:
            text = chunk.get("text", "")
            match = regex.search(text)
            if match:
                candidate = match.group(1).strip("《》「」[]（）() ")
                if 2 <= len(candidate) <= 30:
                    return candidate
    return None


def load_page_counts(interim_root: Path, doc_ids: Iterable[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for doc_id in doc_ids:
        meta_path = interim_root / doc_id / "doc_meta.json"
        page_count = 0
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                page_count = int(meta.get("page_count", 0))
            except Exception:
                page_count = 0
        counts[doc_id] = page_count
    return counts


def prepare_doc_display_names(
    by_doc: Dict[str, List[Dict]],
    name_patterns: List[str],
) -> Dict[str, str]:
    display: Dict[str, str] = {}
    for doc_id, chunks in by_doc.items():
        doc_name = chunks[0].get("doc_name") if chunks else doc_id
        product = guess_product_name(chunks, name_patterns)
        if not product:
            product = norm_prod_name(doc_id, doc_name)
        display[doc_id] = product
    return display


def compile_topic_regex(topics: Dict[str, List[str]]) -> Dict[str, re.Pattern]:
    compiled: Dict[str, re.Pattern] = {}
    for topic, keywords in topics.items():
        if not keywords:
            continue
        pattern = "|".join(re.escape(keyword) for keyword in keywords)
        compiled[topic] = re.compile(pattern)
    return compiled


def major_topic(topic: str) -> str:
    if topic == "annuity":
        return "annuity"
    if topic == "exclusion":
        return "exclusion"
    return "general"


def write_tsv(path: Path, rows: Iterable[Tuple[str, str, int]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(f"{row[0]}\t{row[1]}\t{row[2]}\n")


def build() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", default="corpus/chunks/all_chunks.jsonl")
    parser.add_argument("--interim", default="data/interim")
    parser.add_argument("--terms", default="configs/terms.yaml")
    parser.add_argument("--out", default="testsuite")
    args = parser.parse_args()

    chunks_path = Path(args.chunks)
    interim_root = Path(args.interim)
    terms_cfg = load_yaml(Path(args.terms))

    random.seed(int(terms_cfg.get("random_seed", 42)))

    topics: Dict[str, List[str]] = terms_cfg["topics"]
    name_patterns: List[str] = terms_cfg.get("name_patterns", [])
    query_templates: Dict[str, List[str]] = terms_cfg["query_templates"]
    quotas: Dict[str, int] = terms_cfg.get(
        "quotas", {"annuity": 70, "exclusion": 70, "general": 80}
    )
    limits_cfg: Dict[str, int] = terms_cfg.get(
        "limits", {"max_per_doc_per_topic": 3, "max_total": 220}
    )
    max_per_doc_per_topic = int(limits_cfg.get("max_per_doc_per_topic", 3))
    max_total = int(limits_cfg.get("max_total", 220))
    longdoc_min_pages = int(terms_cfg.get("longdoc", {}).get("min_pages", 10))

    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    chunks = list(read_chunks(chunks_path))
    by_doc: Dict[str, List[Dict]] = defaultdict(list)
    for chunk in chunks:
        by_doc[chunk["doc_id"]].append(chunk)

    doc_display_names = prepare_doc_display_names(by_doc, name_patterns)
    page_counts = load_page_counts(interim_root, by_doc.keys())
    topic_regex = compile_topic_regex(topics)

    candidates: List[Dict] = []
    for chunk in chunks:
        text = chunk.get("text", "")
        doc_id = chunk["doc_id"]
        product = doc_display_names.get(doc_id, doc_id)
        for topic, regex in topic_regex.items():
            if not regex.search(text):
                continue
            templates = query_templates.get(topic, [])
            if not templates:
                continue
            template = random.choice(templates)
            query = template.replace("{prod}", product)
            candidates.append(
                {
                    "major": major_topic(topic),
                    "topic": topic,
                    "query": query,
                    "doc_id": doc_id,
                    "src_chunk_id": chunk["chunk_id"],
                    "prod": product,
                }
            )

    uniq: Dict[Tuple[str, str, str], Dict] = {}
    per_doc_topic: Dict[Tuple[str, str], int] = defaultdict(int)
    by_major: Dict[str, List[Dict]] = defaultdict(list)

    for candidate in candidates:
        key = (candidate["query"], candidate["doc_id"], candidate["major"])
        if key in uniq:
            continue
        doc_topic_key = (candidate["doc_id"], candidate["major"])
        if per_doc_topic[doc_topic_key] >= max_per_doc_per_topic:
            continue
        uniq[key] = candidate
        per_doc_topic[doc_topic_key] += 1
        by_major[candidate["major"]].append(candidate)

    def take_quota(items: List[Dict], quota: int) -> List[Dict]:
        if len(items) <= quota:
            return list(items)
        random.shuffle(items)
        return items[:quota]

    selected: List[Dict] = []
    selected.extend(take_quota(by_major.get("annuity", []), int(quotas.get("annuity", 0))))
    selected.extend(take_quota(by_major.get("exclusion", []), int(quotas.get("exclusion", 0))))
    selected.extend(take_quota(by_major.get("general", []), int(quotas.get("general", 0))))

    if len(selected) > max_total:
        random.shuffle(selected)
        selected = selected[:max_total]

    selected.sort(key=lambda item: (item["major"], item["doc_id"], item["query"]))
    for index, item in enumerate(selected, start=1):
        item["qid"] = f"Q{index:04d}"

    queries_path = output_dir / "queries.jsonl"
    qrels_passage_path = output_dir / "qrels_passage.tsv"
    qrels_doc_path = output_dir / "qrels_doc.tsv"

    qrels_passage: List[Tuple[str, str, int]] = []
    qrels_doc: List[Tuple[str, str, int]] = []

    with queries_path.open("w", encoding="utf-8") as queries_file:
        for item in selected:
            queries_file.write(
                json.dumps(
                    {
                        "qid": item["qid"],
                        "query": item["query"],
                        "topic": item["topic"],
                        "major": item["major"],
                        "doc_id": item["doc_id"],
                        "prod": item["prod"],
                        "src_chunk_id": item["src_chunk_id"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            qrels_passage.append((item["qid"], item["src_chunk_id"], 1))
            qrels_doc.append((item["qid"], item["doc_id"], 1))

    write_tsv(qrels_passage_path, qrels_passage)
    write_tsv(qrels_doc_path, qrels_doc)

    longdoc_ids = sorted(
        doc_id for doc_id, pages in page_counts.items() if pages >= longdoc_min_pages
    )
    (output_dir / "longdoc_ids.txt").write_text(
        "\n".join(longdoc_ids) + ("\n" if longdoc_ids else ""),
        encoding="utf-8",
    )

    stats = {
        "total_queries": len(selected),
        "by_major": dict(Counter(item["major"] for item in selected)),
        "by_topic": dict(Counter(item["topic"] for item in selected)),
        "docs_covered": len({item["doc_id"] for item in selected}),
        "positives_per_qid": dict(Counter(item["qid"] for item in selected)),
        "longdoc_min_pages": longdoc_min_pages,
        "longdoc_count": len(longdoc_ids),
    }
    (output_dir / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    chunk_lookup = {chunk["chunk_id"]: chunk for chunk in chunks}
    checklist_lines: List[str] = ["# Human Checklist (Spot Check)"]
    for major in ["annuity", "exclusion", "general"]:
        subset = [item for item in selected if item["major"] == major]
        random.shuffle(subset)
        subset = subset[:10]
        checklist_lines.append(f"\n## {major}（样本 10）\n")
        for item in subset:
            chunk = chunk_lookup.get(item["src_chunk_id"], {})
            preview = (chunk.get("text", "") or "")[:180]
            checklist_lines.append(
                f"- **{item['qid']}** {item['query']}  \n"
                f"  doc=`{item['doc_id']}` prod=`{item['prod']}`  \n"
                f"  preview: {preview}"
            )

    (output_dir / "human_checklist.md").write_text(
        "\n".join(checklist_lines), encoding="utf-8"
    )

    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build()

