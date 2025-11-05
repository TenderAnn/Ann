"""Rule-based regulatory/ESG tagger with doc-type gating and section awareness."""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import yaml

DEFAULT_NEGATIONS = ["不承担", "免责", "不适用", "不涉及", "无须", "免责说明"]
SECTION_PATTERN = re.compile(r"^((第[一二三四五六七八九十百0-9]+[章节篇条])|([（(][一二三四五六七八九十0-9]+[)）])|([一二三四五六七八九十]+、))", re.MULTILINE)


@dataclass
class Document:
    doc_id: str
    chunk_id: Optional[str]
    text: str
    doc_type: Optional[str]


@dataclass
class Match:
    start: int
    end: int
    snippet: str
    section_name: Optional[str]
    position_bucket: str


@dataclass
class TagHit:
    tag: str
    confidence: float
    matches: List[Match]
    position_bucket: str
    doc_type: Optional[str]


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_lexicon(lexicon_dir: Path) -> Dict[str, List[str]]:
    lexicon: Dict[str, List[str]] = {}
    for txt in lexicon_dir.glob("*.txt"):
        lexicon[txt.stem] = [line.strip() for line in txt.read_text(encoding="utf-8").splitlines() if line.strip()]
    return lexicon


def load_doc_types(path: Optional[Path]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not path or not path.exists():
        return mapping
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            mapping[payload.get("doc_id")] = payload.get("doc_type")
    return mapping


def parse_weights(raw: str, aliases: Iterable[str]) -> Dict[str, float]:
    values = {name: 0.0 for name in aliases}
    for segment in raw.split(","):
        if not segment.strip():
            continue
        if ":" not in segment:
            continue
        key, value = segment.split(":", 1)
        key = key.strip()
        if key in values:
            values[key] = float(value)
    return values


def parse_bins(raw: str) -> List[float]:
    bins = [float(x) for x in raw.split(",") if x.strip()]
    if bins[0] != 0.0:
        bins.insert(0, 0.0)
    if bins[-1] != 1.0:
        bins.append(1.0)
    return bins


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def detect_headings(text: str) -> List[Tuple[int, int, str]]:
    headings: List[Tuple[int, int, str]] = []
    for match in SECTION_PATTERN.finditer(text):
        start = match.start()
        end = text.find("\n", start)
        end = end if end != -1 else start + len(match.group(0))
        headings.append((start, end, match.group(0).strip()))
    return headings


def classify_position(idx: int, headings: List[Tuple[int, int, str]]) -> Tuple[str, Optional[str]]:
    if idx < 150:
        return "title", None
    for start, end, name in headings:
        if start <= idx <= end + 80:
            return "heading", name
    return "body", headings[-1][2] if headings else None


def build_tagging_rules(tagging_config: dict, lexicon: Dict[str, List[str]]) -> Dict[str, dict]:
    rules: Dict[str, dict] = {}
    for tag, cfg in (tagging_config or {}).items():
        include_patterns = _compile_patterns(cfg.get("include", []), lexicon)
        exclude_patterns = _compile_patterns(cfg.get("exclude", []), lexicon)
        negative_cues = cfg.get("negative_cues", []) or DEFAULT_NEGATIONS
        cooccur_patterns = _compile_patterns(cfg.get("cooccur", []), lexicon)
        min_confidence = float(cfg.get("min_confidence", 0.0))
        doc_types = cfg.get("doc_type") or []
        exclude_sections = cfg.get("exclude_sections") or []
        rules[tag] = {
            "include": include_patterns,
            "exclude": exclude_patterns,
            "negative_cues": negative_cues,
            "cooccur": cooccur_patterns,
            "min_confidence": min_confidence,
            "doc_types": doc_types,
            "exclude_sections": exclude_sections,
        }
    return rules


def _compile_patterns(pattern_defs: Iterable[dict], lexicon: Dict[str, List[str]]) -> List[re.Pattern[str]]:
    patterns: List[re.Pattern[str]] = []
    for item in pattern_defs:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "lexicon":
            terms = lexicon.get(item.get("name"), [])
            for term in terms:
                patterns.append(re.compile(re.escape(term), re.IGNORECASE))
            continue
        value = item.get("value") or item.get("pattern")
        if value:
            patterns.append(re.compile(value, re.IGNORECASE))
    return patterns


def load_documents(input_path: Path, doc_types: Dict[str, str]) -> List[Document]:
    docs: List[Document] = []
    if input_path.is_file():
        docs.extend(_load_from_file(input_path, doc_types))
    else:
        for path in sorted(input_path.rglob("*")):
            if path.suffix.lower() in {".txt", ".jsonl"} or path.name.endswith(".chunks.jsonl"):
                docs.extend(_load_from_file(path, doc_types))
    return docs


def _load_from_file(path: Path, doc_types: Dict[str, str]) -> List[Document]:
    if path.suffix.lower() == ".txt":
        doc_id = path.stem
        return [Document(doc_id=doc_id, chunk_id=None, text=path.read_text(encoding="utf-8"), doc_type=doc_types.get(doc_id))]
    records: List[Document] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            text = payload.get("text") or payload.get("content")
            if not text:
                continue
            doc_id = payload.get("doc_id") or path.stem
            records.append(
                Document(
                    doc_id=doc_id,
                    chunk_id=payload.get("chunk_id"),
                    text=text,
                    doc_type=payload.get("doc_type") or doc_types.get(doc_id),
                )
            )
    return records


def _apply_patterns(
    text: str,
    includes: List[re.Pattern[str]],
    negative_cues: List[str],
    excludes: List[re.Pattern[str]],
    skip_keywords: List[str],
    headings: List[Tuple[int, int, str]],
    section_weights: Dict[str, float],
) -> Tuple[List[Match], int, List[str]]:
    for pattern in excludes:
        if pattern.search(text):
            return [], 0, []
    matches: List[Match] = []
    neg_hits = 0
    used_spans = set()
    section_names: List[str] = []
    for pattern in includes:
        for match in pattern.finditer(text):
            span = (match.start(), match.end())
            if span in used_spans:
                continue
            snippet = _extract_snippet(text, match.start(), match.end())
            if any(keyword in snippet for keyword in skip_keywords):
                continue
            if any(cue in snippet for cue in negative_cues):
                neg_hits += 1
                continue
            bucket, section_name = classify_position(match.start(), headings)
            section_names.append(section_name or "")
            matches.append(Match(start=match.start(), end=match.end(), snippet=snippet, section_name=section_name, position_bucket=bucket))
            used_spans.add(span)
    return matches, neg_hits, section_names


def _filter_by_cooccur(
    text: str,
    matches: List[Match],
    cooccurs: List[re.Pattern[str]],
    window: int,
) -> Tuple[List[Match], int]:
    if not cooccurs:
        return matches, len(matches)
    filtered: List[Match] = []
    co_hits = 0
    for match in matches:
        context = text[max(0, match.start - window) : match.end + window]
        if any(pattern.search(context) for pattern in cooccurs):
            filtered.append(match)
            co_hits += 1
    return filtered, co_hits


def _extract_snippet(text: str, start: int, end: int, max_len: int = 200) -> str:
    half = max_len // 2
    snippet = text[max(0, start - half) : end + half]
    return snippet.strip()


def tag_text(
    doc: Document,
    rules: Dict[str, dict],
    skip_keywords: List[str],
    section_weights: Dict[str, float],
    confidence_weights: Dict[str, float],
    cooccur_window: int,
    stats: Dict[str, dict],
) -> List[TagHit]:
    text = doc.text
    headings = detect_headings(text)
    hits: List[TagHit] = []
    for tag, cfg in rules.items():
        if cfg.get("doc_types") and doc.doc_type and doc.doc_type not in cfg["doc_types"]:
            continue
        matches, neg_hits, section_names = _apply_patterns(
            text,
            cfg["include"],
            cfg["negative_cues"],
            cfg["exclude"],
            skip_keywords,
            headings,
            section_weights,
        )
        if not matches:
            continue
        if cfg.get("exclude_sections"):
            matches = [m for m in matches if not _section_blocked(m, cfg["exclude_sections"])]
        if not matches:
            continue
        matches, co_hits = _filter_by_cooccur(text, matches, cfg["cooccur"], cooccur_window)
        if not matches:
            continue
        hits_count = len(matches)
        avg_position = sum(section_weights.get(m.position_bucket, 0.4) for m in matches) / hits_count
        score = (
            confidence_weights["hits"] * math.log1p(hits_count)
            + confidence_weights["position"] * avg_position
            + confidence_weights["cooccur"] * co_hits
            - confidence_weights["neg"] * neg_hits
        )
        confidence = round(sigmoid(score), 4)
        if confidence < cfg.get("min_confidence", 0.0):
            continue
        dominant_bucket = Counter(m.position_bucket for m in matches).most_common(1)[0][0]
        hit = TagHit(tag=tag, confidence=confidence, matches=matches, position_bucket=dominant_bucket, doc_type=doc.doc_type)
        hits.append(hit)
        _update_stats(stats, hit)
    return hits


def _section_blocked(match: Match, blocked: List[str]) -> bool:
    snippet = match.snippet
    if any(keyword in (match.section_name or "") for keyword in blocked):
        return True
    return any(keyword in snippet for keyword in blocked)


def _update_stats(stats: Dict[str, dict], hit: TagHit) -> None:
    bucket_counts = stats.setdefault(hit.tag, {"total": 0, "positions": Counter(), "conf": []})
    bucket_counts["total"] += 1
    bucket_counts["positions"][hit.position_bucket] += 1
    bucket_counts["conf"].append(hit.confidence)


def write_jsonl(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_preview(path: Path, rows: List[dict], sample_size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample = rows if len(rows) <= sample_size else random.sample(rows, sample_size)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["doc_id", "chunk_id", "doc_type", "tags", "confidence", "evidence"])
        for row in sample:
            writer.writerow([
                row["doc_id"],
                row.get("chunk_id"),
                row.get("doc_type"),
                ";".join(row.get("tags", [])),
                row.get("confidence", 0.0),
                " | ".join(row.get("evidence", [])),
            ])


def write_stats(path: Path, stats: Dict[str, dict], bins: List[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = ["tag", "total", "title_hits", "heading_hits", "body_hits", "avg_confidence"]
    bin_headers = []
    for i in range(len(bins) - 1):
        bin_headers.append(f"bin_{bins[i]:.2f}_{bins[i+1]:.2f}")
    headers.extend(bin_headers)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for tag, info in stats.items():
            conf_values = info["conf"]
            avg_conf = sum(conf_values) / len(conf_values) if conf_values else 0.0
            row = [
                tag,
                info.get("total", 0),
                info["positions"].get("title", 0),
                info["positions"].get("heading", 0),
                info["positions"].get("body", 0),
                round(avg_conf, 4),
            ]
            hist = _histogram(conf_values, bins)
            row.extend(hist)
            writer.writerow(row)


def _histogram(values: List[float], bins: List[float]) -> List[int]:
    counts = [0 for _ in range(len(bins) - 1)]
    for value in values:
        for i in range(len(bins) - 1):
            if bins[i] <= value < bins[i + 1]:
                counts[i] += 1
                break
        else:
            counts[-1] += 1
    return counts


def run_tagger(args: argparse.Namespace) -> None:
    taxonomy = load_yaml(Path(args.taxonomy))
    rulebook = load_yaml(Path(args.rulebook))
    lexicon = load_lexicon(Path(args.lexicon_dir))
    rules = build_tagging_rules(rulebook.get("tagging"), lexicon)
    allowed_tags = {child["id"] for domain in taxonomy.get("domains", []) for child in domain.get("children", [])}
    unknown = set(rules) - allowed_tags
    if unknown:
        print(f"Warning: rules defined for unknown taxonomy tags: {sorted(unknown)}")
    doc_types = load_doc_types(Path(args.doc_type_map) if args.doc_type_map else None)
    documents = load_documents(Path(args.input), doc_types)

    skip_keywords = [kw.strip() for kw in args.skip_sections.split(",") if kw.strip()]
    section_weights = parse_weights(args.section_weight, ["title", "heading", "body"])
    confidence_weights = parse_weights(args.confidence_weights, ["hits", "position", "cooccur", "neg"])
    histogram_bins = parse_bins(args.histogram_bins)

    start = time.perf_counter()
    rows: List[dict] = []
    tag_counter: Counter[str] = Counter()
    stats: Dict[str, dict] = {}

    for doc in documents:
        hits = tag_text(doc, rules, skip_keywords, section_weights, confidence_weights, args.cooccur_window, stats)
        if not hits:
            continue
        tags = [hit.tag for hit in hits]
        tag_counter.update(tags)
        rows.append(
            {
                "doc_id": doc.doc_id,
                "chunk_id": doc.chunk_id,
                "doc_type": doc.doc_type,
                "tags": tags,
                "confidence": max(hit.confidence for hit in hits),
                "evidence": [hit.matches[0].snippet for hit in hits if hit.matches],
                "tag_details": [
                    {
                        "name": hit.tag,
                        "confidence": hit.confidence,
                        "position": hit.position_bucket,
                        "doc_type": hit.doc_type,
                        "evidence": [m.snippet for m in hit.matches[:2]],
                    }
                    for hit in hits
                ],
            }
        )

    write_jsonl(Path(args.out), rows)
    write_preview(Path(args.preview), rows, args.sample_size)
    write_stats(Path(args.stats_out), stats, histogram_bins)

    elapsed = time.perf_counter() - start
    print(f"Processed {len(documents)} segments in {elapsed:.2f}s; hits: {sum(tag_counter.values())}")
    for tag, count in tag_counter.most_common():
        print(f"  - {tag}: {count}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regulatory/ESG tagger")
    parser.add_argument("--in", dest="input", required=True)
    parser.add_argument("--taxonomy", required=True)
    parser.add_argument("--rulebook", required=True)
    parser.add_argument("--lexicon_dir", required=True)
    parser.add_argument("--doc-type-map", default="data/metadata/doc_types.jsonl")
    parser.add_argument("--out", required=True)
    parser.add_argument("--preview", required=True)
    parser.add_argument("--stats-out", default="samples/tagging_stats.csv")
    parser.add_argument("--sample_size", type=int, default=50)
    parser.add_argument("--skip-sections", default="目录,索引,封面,封底,版权页,广告页")
    parser.add_argument("--section-weight", default="title:1.0,heading:0.7,body:0.4")
    parser.add_argument("--confidence-weights", default="hits:1.0,position:1.0,cooccur:0.8,neg:1.0")
    parser.add_argument("--histogram-bins", default="0.0,0.2,0.4,0.6,0.8,1.0")
    parser.add_argument("--cooccur-window", type=int, default=40)
    return parser.parse_args()


def main() -> None:
    run_tagger(parse_args())


if __name__ == "__main__":
    main()
