from __future__ import annotations

from receipt_reader.models import (
    Comparison,
    Confidence,
    ExtractedField,
    ExtractedReceipt,
    LineItem,
    MatchResult,
    ReceiptStatus,
    ReceiptType,
)
from receipt_reader.summarize import build_summary, decide_status, found_and_missing


def test_summary_format_and_found_missing():
    extracted = ExtractedReceipt(
        merchant=ExtractedField(value="Prime Cut", confidence=Confidence.high),
        date=ExtractedField(value="2026-06-25", confidence=Confidence.high),
        total=ExtractedField(value=150.0, confidence=Confidence.high),
        currency=ExtractedField(value="USD", confidence=Confidence.medium),
        tax=ExtractedField(value=12.0, confidence=Confidence.high),
        tip=ExtractedField(value=25.0, confidence=Confidence.medium),
        line_items=[LineItem(description="Heineken beer", quantity=1, amount=15.0, is_alcohol=True)],
        alcohol_detected=True,
        receipt_type=ReceiptType.itemized,
    )
    comparison = Comparison(
        performed=True,
        amount_match=MatchResult(result="match", claimed=150.0, receipt=150.0, diff=0.0),
    )
    summary = build_summary(extracted, comparison)
    assert "Prime Cut" in summary
    assert "2026-06-25" in summary
    assert "$150.00" in summary
    assert "USD" in summary
    assert "alcohol" in summary
    assert "matches claimed amount" in summary
    assert len(summary) <= 200
    found, missing = found_and_missing(extracted)
    assert "merchant" in found and "total" in found
    assert "payment_last4" in missing


def test_summary_without_claim_and_unknown_merchant():
    extracted = ExtractedReceipt(
        date=ExtractedField(value="2026-01-01", confidence=Confidence.high),
        total=ExtractedField(value=10.0, confidence=Confidence.high),
        currency=ExtractedField(value="USD", confidence=Confidence.high),
    )
    summary = build_summary(extracted, Comparison(performed=False))
    assert "merchant unknown" in summary
    assert "no claim to compare" in summary


def test_status_ok_vs_partial_vs_unreadable():
    ok = ExtractedReceipt(
        merchant=ExtractedField(value="A", confidence=Confidence.high),
        date=ExtractedField(value="2026-01-01", confidence=Confidence.medium),
        total=ExtractedField(value=1.0, confidence=Confidence.high),
        currency=ExtractedField(value="USD", confidence=Confidence.medium),
    )
    assert decide_status(ok, ["merchant", "date", "total", "currency"]) is ReceiptStatus.ok
    low = ExtractedReceipt(
        merchant=ExtractedField(value="A", confidence=Confidence.low),
        date=ExtractedField(value="2026-01-01", confidence=Confidence.high),
        total=ExtractedField(value=1.0, confidence=Confidence.high),
        currency=ExtractedField(value="USD", confidence=Confidence.high),
    )
    assert decide_status(low, ["merchant", "date", "total", "currency"]) is ReceiptStatus.partial
    assert decide_status(ok, [], is_receipt=False) is ReceiptStatus.unreadable
