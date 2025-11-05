from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from api.utils_norm import (
    build_reverse_map,
    cn_digit_to_int,
    load_ontology,
    load_synonyms,
    normalize_text,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
ONTOLOGY = load_ontology(DATA_DIR / "ontology_insurance_zh.yaml")
SYNONYMS = load_synonyms(DATA_DIR / "synonyms_insurance_zh_v1.1.tsv")
REV_MAP = build_reverse_map(SYNONYMS)


def _alias_cases(limit: int = 50):
    pairs = []
    for canonical, aliases in SYNONYMS.items():
        for alias in aliases:
            alias = alias.strip()
            if not alias or alias == canonical:
                continue
            pairs.append((alias, canonical))
            if len(pairs) >= limit:
                return pairs
    return pairs


ALIAS_CASES = _alias_cases(55)


def test_synonym_table_loaded():
    assert len(SYNONYMS) > 0
    assert any("养老/年金" in key for key in SYNONYMS)


def test_reverse_map_contains_canonical():
    assert REV_MAP["养老/年金"] == "养老/年金"


@pytest.mark.parametrize(
    "alias, canonical",
    ALIAS_CASES,
)
def test_normalize_maps_aliases(alias: str, canonical: str):
    text = f"想了解下{alias}产品的权益"
    normalized = normalize_text(text, REV_MAP)
    assert canonical in normalized


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("能不能 查查 yanglao shequ 的保险 等带期 多久", "CCRC资格权益"),
        ("想了解快返型5年返的寿险", "生存金短期返还(≤5年)"),
        ("观察期 30 日需要等多久", "30天"),
        ("冷静期是几天", "犹豫期"),
        ("终寿 2024 版本", "2024"),
        ("我想问问趸交是不是一次性交费", "趸交"),
    ],
)
def test_normalize_handles_noise(raw: str, expected: str):
    normalized = normalize_text(raw, REV_MAP)
    assert expected in normalized
    assert "能不能" not in normalized


@pytest.mark.parametrize(
    "text, expected",
    [
        ("十", 10),
        ("十五", 15),
        ("二十", 20),
        ("二十五", 25),
        ("三十六", 36),
        ("五十五", 55),
        ("六十", 60),
        ("七十", 70),
        ("八十九", 89),
        ("九十", 90),
    ],
)
def test_cn_digit_to_int(text: str, expected: int):
    assert cn_digit_to_int(text) == expected


def test_normalize_whitespace_and_case():
    raw = "   年金 险   2024  版   "
    normalized = normalize_text(raw, REV_MAP)
    assert "养老/年金" in normalized
    assert "2024" in normalized
    assert "  " not in normalized
