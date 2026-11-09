from __future__ import annotations

from receipt_reader.compare import compare_claim, merchant_overlap
from receipt_reader.config import Settings
from receipt_reader.models import (
    ClaimedExpense,
    Confidence,
    ExtractedField,
    ExtractedReceipt,
    LineItem,
)

SETTINGS = Settings(
    api_key="test",
    model="test",
    ocr_model="test",
    base_url="https://openrouter.ai/api/v1",
    max_pages=5,
    vision_max_pages=2,
    amount_tolerance_usd=1.0,
    amount_tolerance_pct=2.0,
)


def _extracted(**kwargs) -> ExtractedReceipt:
    defaults = dict(
        merchant=ExtractedField(value="Prime Cut", confidence=Confidence.high),
        date=ExtractedField(value="2026-06-25", confidence=Confidence.high),
        total=ExtractedField(value=150.0, confidence=Confidence.high),
        currency=ExtractedField(value="USD", confidence=Confidence.medium),
    )
    defaults.update(kwargs)
    return ExtractedReceipt(**defaults)


def test_amount_match_within_dollar():
    comparison, warnings = compare_claim(
        _extracted(),
        ClaimedExpense(amount=149.50, currency="USD"),
        SETTINGS,
    )
    assert comparison.amount_match.result == "match"
    assert "AMOUNT_MISMATCH" not in warnings


def test_amount_mismatch_ten_dollars():
    comparison, warnings = compare_claim(
        _extracted(),
        ClaimedExpense(amount=140.0, currency="USD"),
        SETTINGS,
    )
    assert comparison.amount_match.result == "mismatch"
    assert comparison.amount_match.diff == 10.0
    assert "AMOUNT_MISMATCH" in warnings


def test_currency_differs_skips_amount_mismatch():
    comparison, warnings = compare_claim(
        _extracted(currency=ExtractedField(value="EUR", confidence=Confidence.high), total=ExtractedField(value=65.0, confidence=Confidence.high)),
        ClaimedExpense(amount=65.0, currency="USD"),
        SETTINGS,
    )
    assert "CURRENCY_DIFFERS" in warnings
    assert "AMOUNT_MISMATCH" not in warnings
    assert comparison.amount_match.result == "unknown"


def test_date_off_by_one_is_warning_not_mismatch():
    comparison, warnings = compare_claim(
        _extracted(),
        ClaimedExpense(amount=150.0, date="2026-06-26"),
        SETTINGS,
    )
    assert comparison.date_match.result == "match"
    assert "DATE_OFF_BY_ONE_DAY" in warnings
    assert "DATE_MISMATCH" not in warnings


def test_date_mismatch_beyond_one_day():
    _, warnings = compare_claim(
        _extracted(),
        ClaimedExpense(amount=150.0, date="2026-06-20"),
        SETTINGS,
    )
    assert "DATE_MISMATCH" in warnings


def test_sq_star_descriptor_matches_merchant():
    assert merchant_overlap("SQ *SQ COFFEE", "SQ Coffee") >= 0.5
    comparison, warnings = compare_claim(
        _extracted(merchant=ExtractedField(value="SQ *SQ COFFEE", confidence=Confidence.high)),
        ClaimedExpense(amount=150.0, merchant="SQ Coffee"),
        SETTINGS,
    )
    assert comparison.merchant_match.result == "match"
    assert "MERCHANT_MISMATCH" not in warnings


def test_alcohol_not_in_memo():
    extracted = _extracted(
        alcohol_detected=True,
        line_items=[LineItem(description="Heineken beer", quantity=1, amount=15.0, is_alcohol=True)],
    )
    _, warnings = compare_claim(extracted, ClaimedExpense(amount=150.0, memo="team dinner"), SETTINGS)
    assert "ALCOHOL_NOT_MENTIONED_IN_MEMO" in warnings
    _, warnings2 = compare_claim(extracted, ClaimedExpense(amount=150.0, memo="wine with dinner"), SETTINGS)
    assert "ALCOHOL_NOT_MENTIONED_IN_MEMO" not in warnings2
