# -*- coding: utf-8 -*-
"""Table header alias mapping for canonical fields."""
ALIASES = {
    # 基础字段
    "投保年龄": "age",
    "年龄(周岁)": "age",
    "周岁": "age",
    "age (years)": "age",
    "age": "age",
    "等待期": "waiting_period",
    "waiting period": "waiting_period",
    "犹豫期": "cooling_off",
    "交费年期": "pay_years",
    "保险期间": "coverage_term",
    "职业类别": "occupation_class",
    # 费率/金额/比例
    "年交保费": "annual_premium",
    "annual premium": "annual_premium",
    "月交保费": "monthly_premium",
    "基本保额": "sum_assured",
    "保额": "sum_assured",
    "sum assured": "sum_assured",
    "费率": "rate",
    "保费": "premium",
    "价格": "price",
    # 产品字段
    "产品名称": "product_name",
    "版本": "version_year",
    "product name": "product_name",
}

def normalize_header(s: str) -> str:
    s = (s or "").strip().replace("\u00a0", " ").replace("\t", " ")
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("　", " ")
    return s


def to_canonical(header: str) -> str:
    h = normalize_header(header)
    for k, v in ALIASES.items():
        if k in h:
            return v
    return h
