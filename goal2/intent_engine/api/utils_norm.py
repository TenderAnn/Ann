"""Text normalization and rule-based slot extraction utilities."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Pattern, Tuple

import yaml

FULL2HALF = str.maketrans({chr(0x3000): " "})

# Common conversational fillers to drop before pattern matching.
STOP_PHRASES = [
    "能不能",
    "有没有",
    "想了解下",
    "想了解一下",
    "麻烦",
    "帮我查查",
    "帮我问问",
    "我想问问",
    "请问",
    "看看",
    "了解下",
    "可以告诉我",
    "想知道",
]

UNIT_PATTERNS = [
    (re.compile(r"(\d+)\s*周岁"), r"\1岁"),
    (re.compile(r"(\d+)\s*个?工作日"), r"\1天"),
    (re.compile(r"(\d+)\s*个?月"), r"\1个月"),
    (re.compile(r"(\d+)\s*日"), r"\1天"),
]

CN_NUM = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _compile_trigger_map(raw: Mapping[str, Iterable[str]]) -> Dict[str, List[Pattern[str]]]:
    return {key: [re.compile(pattern, re.IGNORECASE) for pattern in patterns] for key, patterns in raw.items()}


BENEFIT_TRIGGER_PATTERNS = _compile_trigger_map(
    {
        "CCRC资格权益": [
            r"ccrc",
            r"养老社区",
            r"康养社区",
            r"医养",
            r"持续照护",
            r"持续照料退休社区",
            r"入住资格",
            r"养老公寓",
            r"养老床位",
        ],
        "生存金短期返还(≤5年)": [
            r"快返型?",
            r"返得快",
            r"早返",
            r"(?:五|5)年返",
            r"短期返(?:还)?",
            r"定期返还",
            r"逐年返",
            r"年年返",
            r"返本",
            r"返还金",
            r"提前返",
        ],
        "红利/分红": [
            r"红利(领取|账户|派发)",
            r"分红(领取|派发|怎么|如何|说明|收益)",
            r"红利收益",
        ],
        "护理权益": [
            r"护理服务",
            r"护理权益",
            r"护理津贴",
            r"护理床位",
            r"护理社区",
            r"照护",
            r"长期照护",
        ],
        "年金领取": [
            r"年金发放",
            r"年金领取",
            r"养老金领取",
            r"领钱",
        ],
        "意外保障": [
            r"意外伤害",
            r"意外身故",
            r"意外残疾",
            r"交通意外",
            r"意外保障",
        ],
        "现金价值": [
            r"现金价值",
            r"现金值",
            r"现价",
            r"现金价值积累",
        ],
    }
)

FIELD_TRIGGER_PATTERNS = _compile_trigger_map(
    {
        "投保年龄": [
            r"投保年龄",
            r"年龄(上限|范围|限制)",
            r"年龄段",
        ],
        "交费年期": [
            r"(?:交|缴)费(年期|期限)",
            r"交几(?:年|期)",
        ],
        "保障期间": [
            r"(?:保险|保障)期间",
            r"保障期",
        ],
        "等待期": [
            r"等待期",
            r"免责期",
            r"观察期",
        ],
        "犹豫期": [
            r"犹豫期",
            r"冷静期",
        ],
        "理赔流程": [
            r"理赔流程",
            r"怎么赔",
            r"如何理赔",
        ],
        "理赔材料": [
            r"理赔材料",
            r"需要什么材料",
        ],
        "保费/费率": [
            r"保费",
            r"费率",
            r"多少钱",
            r"价格",
        ],
        "保险金额": [
            r"保额",
            r"保险金额",
        ],
        "职业类别": [
            r"职业类别",
            r"职业等级",
            r"工种等级",
        ],
        "健康告知": [
            r"健康告知",
            r"健康问卷",
            r"核保问题",
        ],
    }
)


def load_ontology(path: str | Path) -> dict:
    """Load ontology yaml into Python dict."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_synonyms(path: str | Path) -> Dict[str, List[str]]:
    """Load canonical -> aliases mapping from TSV."""
    synonyms: Dict[str, List[str]] = {}
    with open(path, "r", encoding="utf-8") as f:
        header = f.readline()
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            canonical, alias = parts
            canonical = canonical.strip()
            alias = alias.strip()
            if not canonical or not alias:
                continue
            synonyms.setdefault(canonical, [])
            if alias not in synonyms[canonical]:
                synonyms[canonical].append(alias)
    return synonyms


def _han_score(text: str) -> int:
    return sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")


def build_reverse_map(syn: Mapping[str, Iterable[str]]) -> Dict[str, str]:
    """Convert canonical -> aliases into alias -> canonical map."""
    rev: Dict[str, str] = {}
    scores: Dict[str, int] = {}
    for canonical, aliases in syn.items():
        values = list(aliases) if isinstance(aliases, list) else list(aliases)
        values.append(canonical)
        for alias in values:
            token = alias.strip().lower()
            if not token:
                continue
            score = _han_score(canonical)
            if token not in rev or score > scores.get(token, -1):
                rev[token] = canonical
                scores[token] = score
    # Resolve chained canonical mappings so indirect aliases collapse to a root term.
    for token, canonical in list(rev.items()):
        root = canonical
        visited = set()
        while True:
            lookup = root.strip().lower()
            if lookup in visited:
                break
            visited.add(lookup)
            next_root = rev.get(lookup)
            if not next_root or next_root == root:
                break
            root = next_root
        rev[token] = root
    return rev


def cn_digit_to_int(text: str) -> Optional[int]:
    """Convert small Chinese numerals (<= 99) to integers."""
    if not text:
        return None
    result = 0
    current = 0
    has_digit = False
    for ch in text:
        if ch not in CN_NUM and ch != "十":
            continue
        has_digit = True
        if ch == "十":
            current = current or 1
            result += current * 10
            current = 0
        else:
            current = current * 10 + CN_NUM[ch]
    result += current
    return result if has_digit and result > 0 else None


def _remove_stop_phrases(text: str) -> str:
    for phrase in STOP_PHRASES:
        text = text.replace(phrase, " ")
    return text


def _apply_unit_normalization(text: str) -> str:
    updated = text
    for pattern, repl in UNIT_PATTERNS:
        updated = pattern.sub(repl, updated)
    return updated


def normalize_text(text: str | None, rev_map: Mapping[str, str]) -> str:
    """Normalize colloquial text into canonical-friendly representation."""
    if text is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(text)).translate(FULL2HALF)
    normalized = _remove_stop_phrases(normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    # Apply synonym replacements, longest alias first.
    if rev_map:
        tokens = sorted(rev_map.items(), key=lambda kv: len(kv[0]), reverse=True)
        placeholders: Dict[str, str] = {}
        counter = 0

        for alias, canonical in tokens:
            if not alias:
                continue
            pattern = re.compile(re.escape(alias), flags=re.IGNORECASE)

            def _repl(match, canonical=canonical):
                nonlocal counter
                placeholder = f"__CANONICAL_{counter}__"
                placeholders[placeholder] = canonical
                counter += 1
                return placeholder

            normalized = pattern.sub(_repl, normalized)

        for placeholder, canonical in placeholders.items():
            normalized = normalized.replace(placeholder, canonical)

    normalized = _apply_unit_normalization(normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def first_trigger_hit(trigger_map: Mapping[str, List[Pattern[str]]], text: str) -> Optional[str]:
    for key, regexes in trigger_map.items():
        for regex in regexes:
            if regex.search(text):
                return key
    return None


def _match_from_section(text: str, section: Mapping[str, Iterable[str]]) -> Optional[str]:
    if not section:
        return None
    candidates: List[Tuple[int, str]] = []
    lowered = text.lower()
    for canonical, aliases in section.items():
        variants = [canonical]
        if aliases:
            variants.extend(aliases)
        for alias in variants:
            alias_norm = alias.strip()
            if not alias_norm:
                continue
            if alias_norm.lower() in lowered:
                candidates.append((len(alias_norm), canonical))
                break
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def detect_version_year(text: str) -> Optional[str]:
    match = re.search(r"(20\d{2})\s*(?:年|年度)?\s*(?:版|版本|款)?", text)
    if match:
        return match.group(1)
    short = re.search(r"(?:['’](\d{2})|(\d{2}))\s*(?:版|版本|款)", text)
    if short:
        yy = short.group(1) or short.group(2)
        if yy:
            value = int(yy)
            if 15 <= value <= 39:
                return f"20{value:02d}"
    return None


def _norm_age(text: str) -> Tuple[Optional[int], Optional[int]]:
    range_match = re.search(r"(\d{1,2})\s*[-~至到——]\s*(\d{1,2})\s*(?:岁|周岁)?", text)
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2))
    single = re.search(r"(\d{1,2})\s*(?:岁|周岁)", text)
    if single:
        age = int(single.group(1))
        return age, age
    cn = re.search(r"([一二三四五六七八九十两]{1,3})\s*(?:岁|周岁)", text)
    if cn:
        val = cn_digit_to_int(cn.group(1))
        if val:
            return val, val
    return None, None


def _norm_pay_years(text: str) -> Optional[str]:
    numeric = re.search(r"(?:交|缴)[^0-9]{0,4}?(\d{1,2})\s*年", text)
    if numeric:
        return str(int(numeric.group(1)))
    trailing = re.search(r"(\d{1,2})\s*年\s*(?:交|缴)", text)
    if trailing:
        return str(int(trailing.group(1)))
    cn_prefix = re.search(r"(?:交|缴)[^0-9]{0,4}?([一二三四五六七八九十两]{1,3})\s*年", text)
    if cn_prefix:
        val = cn_digit_to_int(cn_prefix.group(1))
        if val:
            return str(val)
    cn = re.search(r"([一二三四五六七八九十两]{1,3})\s*年\s*(?:交|缴)", text)
    if cn:
        val = cn_digit_to_int(cn.group(1))
        if val:
            return str(val)
    if "趸交" in text or "一次性" in text:
        return "趸交"
    return None


def _norm_wait(text: str) -> Tuple[Optional[int], Optional[str]]:
    match = re.search(r"(\d{1,3})\s*(天|日|个月|月)", text)
    if match:
        return int(match.group(1)), match.group(2)
    cn = re.search(r"([一二三四五六七八九十两]{1,3})\s*(天|日|个月|月)", text)
    if cn:
        val = cn_digit_to_int(cn.group(1))
        if val:
            return val, cn.group(2)
    return None, None


def rule_slots(text: str | None, ontology: Mapping[str, object], rev_map: Mapping[str, str]) -> Dict[str, str]:
    """Extract structured slots from colloquial text using ontology hints."""
    normalized = normalize_text(text or "", rev_map)
    slots: Dict[str, str] = {}

    product_line = _match_from_section(normalized, ontology.get("product_lines", {}))
    if product_line and product_line != "未知":
        slots["product_line"] = product_line

    benefit_type = first_trigger_hit(BENEFIT_TRIGGER_PATTERNS, normalized)
    if not benefit_type:
        benefit_type = _match_from_section(normalized, ontology.get("benefit_types", {}))
    if benefit_type:
        slots["benefit_type"] = benefit_type

    field = first_trigger_hit(FIELD_TRIGGER_PATTERNS, normalized)
    if not field:
        field = _match_from_section(normalized, ontology.get("fields", {}))
    if field:
        slots["field"] = field

    version = detect_version_year(normalized)
    if version:
        slots["version_year"] = version

    age_min, age_max = _norm_age(normalized)
    if age_min is not None and age_max is not None:
        slots["age_min"] = str(age_min)
        slots["age_max"] = str(age_max)
        if age_min == age_max:
            slots["age"] = str(age_min)

    pay_years = _norm_pay_years(normalized)
    if pay_years:
        slots["pay_years"] = pay_years

    wait_value, wait_unit = _norm_wait(normalized)
    if wait_value:
        unit = "天" if wait_unit in {"日"} else wait_unit
        slots["waiting_period"] = f"{wait_value}{unit or ''}"
        slots["waiting_value"] = str(wait_value)
        if unit:
            slots["waiting_unit"] = unit

    return slots


__all__ = [
    "STOP_PHRASES",
    "BENEFIT_TRIGGER_PATTERNS",
    "FIELD_TRIGGER_PATTERNS",
    "load_ontology",
    "load_synonyms",
    "build_reverse_map",
    "normalize_text",
    "rule_slots",
    "cn_digit_to_int",
    "first_trigger_hit",
    "detect_version_year",
]
