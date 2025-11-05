from regulatory.scripts.tag_regulatory import (
    Document,
    build_tagging_rules,
    tag_text,
)

LEXICON = {
    "esg": ["ESG", "责任投资"],
    "rating": ["监管评级"],
    "consumer_protection": ["投诉处理"],
    "disclosure_gov": ["信息披露"],
}

TAG_CFG = {
    "esg": {
        "include": [{"type": "lexicon", "name": "esg"}],
        "negative_cues": ["免责"],
        "doc_type": ["ESG报告"],
        "min_confidence": 0.4,
    },
    "rating": {
        "include": [{"type": "lexicon", "name": "rating"}],
        "cooccur": [{"type": "regex", "value": "通报"}],
        "min_confidence": 0.3,
    },
    "consumer_protection": {"include": [{"type": "lexicon", "name": "consumer_protection"}]},
    "disclosure_gov": {"include": [{"type": "lexicon", "name": "disclosure_gov"}]},
}

SECTION_WEIGHTS = {"title": 1.0, "heading": 0.7, "body": 0.4}
CONF_WEIGHTS = {"hits": 1.0, "position": 1.0, "cooccur": 0.5, "neg": 1.0}


def _rules():
    return build_tagging_rules(TAG_CFG, LEXICON)


def _run(text: str, doc_type: str | None = None):
    doc = Document(doc_id="doc", chunk_id=None, text=text, doc_type=doc_type)
    stats = {}
    return tag_text(doc, _rules(), [], SECTION_WEIGHTS, CONF_WEIGHTS, 40, stats)


def test_positive_hit_detects_esg_with_valid_doc_type():
    hits = _run("【ESG报告】本产品强调ESG责任投资策略", doc_type="ESG报告")
    assert any(hit.tag == "esg" for hit in hits)


def test_doc_type_blocks_esg_when_not_allowed():
    hits = _run("【年度报告】本产品强调ESG责任投资策略", doc_type="年度报告")
    assert all(hit.tag != "esg" for hit in hits)


def test_negative_cue_blocks_hit():
    hits = _run("ESG条款仅做免责说明", doc_type="ESG报告")
    assert all(hit.tag != "esg" for hit in hits)


def test_cooccur_required_for_rating():
    hits = _run("监管评级需要信息披露", doc_type="监管通报")
    assert all(hit.tag != "rating" for hit in hits)
    hits = _run("监管评级通报要求整改", doc_type="监管通报")
    assert any(hit.tag == "rating" for hit in hits)


def test_multiple_tags_returned():
    hits = _run("监管评级通报要求信息披露", doc_type="监管通报")
    tags = {hit.tag for hit in hits}
    assert tags == {"rating", "disclosure_gov"}


def test_no_hit_returns_empty_list():
    hits = _run("普通产品说明", doc_type="销售信函")
    assert hits == []
