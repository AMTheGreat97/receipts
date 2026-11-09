from __future__ import annotations

import os

import pytest

from receipt_reader.config import load_settings
from receipt_reader.models import ClaimedExpense, ExtractMode, ReceiptStatus
from receipt_reader.reader import read_receipt

pytestmark = pytest.mark.live


def _has_key() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY", "").strip() or load_settings().api_key)


@pytest.mark.skipif(not _has_key(), reason="OPENROUTER_API_KEY not set")
def test_live_itemized_vision(fixtures):
    result = read_receipt(fixtures["itemized.png"], mode=ExtractMode.vision)
    assert result.status in {ReceiptStatus.ok, ReceiptStatus.partial}
    assert result.meta.is_receipt is True
    assert result.extracted.total and result.extracted.total.value is not None


@pytest.mark.skipif(not _has_key(), reason="OPENROUTER_API_KEY not set")
def test_live_non_receipt(fixtures):
    result = read_receipt(fixtures["non_receipt.png"], mode=ExtractMode.vision)
    assert result.status is ReceiptStatus.unreadable or "NOT_A_RECEIPT" in result.warnings
