from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from api.utils_norm import build_reverse_map, load_ontology, load_synonyms, rule_slots

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
ONTOLOGY = load_ontology(DATA_DIR / "ontology_insurance_zh.yaml")
SYNONYMS = load_synonyms(DATA_DIR / "synonyms_insurance_zh_v1.1.tsv")
REV_MAP = build_reverse_map(SYNONYMS)

SLOT_CASES = [
    (
        "年金险等待期30天要多久",
        {
            "product_line": "养老/年金",
            "field": "等待期",
            "waiting_period": "30天",
            "waiting_value": "30",
            "waiting_unit": "天",
        },
    ),
    (
        "终寿快返型产品5年返 2022版本 18-55周岁",
        {
            "product_line": "终身寿险",
            "benefit_type": "生存金短期返还(≤5年)",
            "version_year": "2022",
            "age_min": "18",
            "age_max": "55",
        },
    ),
    (
        "养老社区的保险交十五年吗",
        {
            "benefit_type": "CCRC资格权益",
            "pay_years": "15",
        },
    ),
    (
        "重疾险观察期九十天是多少",
        {
            "product_line": "重疾保险",
            "field": "等待期",
            "waiting_period": "90天",
        },
    ),
    (
        "意外险职业等级怎么卡",
        {
            "product_line": "意外保险",
            "field": "职业类别",
        },
    ),
    (
        "增额寿2023年版交费年期20年吗",
        {
            "product_line": "增额终身寿险",
            "version_year": "2023",
            "field": "交费年期",
            "pay_years": "20",
        },
    ),
    (
        "理赔需要什么材料",
        {
            "field": "理赔材料",
        },
    ),
    (
        "理赔流程怎么走",
        {
            "field": "理赔流程",
        },
    ),
    (
        "趸交可以一次性交完吗",
        {
            "pay_years": "趸交",
        },
    ),
    (
        "冷静期一般多长",
        {
            "field": "犹豫期",
        },
    ),
    (
        "护理险职业等级要求",
        {
            "product_line": "护理保险",
            "field": "职业类别",
        },
    ),
    (
        "年金领取方式有哪些",
        {
            "benefit_type": "年金领取",
        },
    ),
    (
        "护理服务权益包含什么",
        {
            "benefit_type": "护理权益",
        },
    ),
    (
        "意外身故/伤残保障怎么写",
        {
            "benefit_type": "意外保障",
        },
    ),
    (
        "保费豁免条款触发条件",
        {
            "benefit_type": "保费豁免",
        },
    ),
    (
        "现价能不能提前取",
        {
            "benefit_type": "现金价值",
        },
    ),
    (
        "红利怎么分配",
        {
            "benefit_type": "红利/分红",
        },
    ),
    (
        "大病保障包含多少疾病",
        {
            "benefit_type": "重疾保障",
        },
    ),
    (
        "保额设置多少",
        {
            "field": "保险金额",
        },
    ),
    (
        "费率怎么算",
        {
            "field": "保费/费率",
        },
    ),
    (
        "健康问卷要求严格吗",
        {
            "field": "健康告知",
        },
    ),
    (
        "可投年龄18~60周岁吗",
        {
            "field": "投保年龄",
            "age_min": "18",
            "age_max": "60",
        },
    ),
    (
        "55周岁还能买终寿吗",
        {
            "product_line": "终身寿险",
            "age": "55",
        },
    ),
    (
        "观察期三十天吧",
        {
            "field": "等待期",
            "waiting_period": "30天",
        },
    ),
    (
        "等待期6个月吗",
        {
            "field": "等待期",
            "waiting_period": "6个月",
        },
    ),
    (
        "等待期90日是多久",
        {
            "field": "等待期",
            "waiting_period": "90天",
            "waiting_unit": "天",
        },
    ),
]


@pytest.mark.parametrize("query, expected", SLOT_CASES)
def test_rule_slots_expected_outputs(query: str, expected: dict):
    slots = rule_slots(query, ONTOLOGY, REV_MAP)
    for key, value in expected.items():
        assert slots.get(key) == value


def test_rule_slots_handles_none():
    assert rule_slots(None, ONTOLOGY, REV_MAP) == {}
