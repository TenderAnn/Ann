from datetime import datetime

from freshrank.extractors.date_status_extractor import parse_temporal_fields


def test_parse_temporal_fields_extracts_effective_date():
    text = "本条款生效日期为2024年1月1日，废止日期为2025年12月31日。"
    metadata = parse_temporal_fields(text, collected_at=datetime(2024, 6, 1))
    assert metadata.effective_date.year == 2024
    assert metadata.expiry_date.year == 2025
    assert metadata.is_expired is False
