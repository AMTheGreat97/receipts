from __future__ import annotations

import re
from datetime import date

from receipt_reader.config import Settings
from receipt_reader.models import (
    ClaimedExpense,
    Comparison,
    ExtractedReceipt,
    MatchResult,
)

_STOPWORDS = {"the", "inc", "llc", "ltd", "co", "corp", "company"}
_ALCOHOL_MEMO_WORDS = (
    "beer",
    "wine",
    "drinks",
    "cocktail",
    "bar",
    "alcohol",
    "liquor",
    "whiskey",
    "whisky",
    "vodka",
    "gin",
    "rum",
    "tequila",
    "cider",
    "champagne",
    "prosecco",
    "sake",
    "ipa",
)


def field_value(field) -> object | None:
    if field is None:
        return None
    return field.value


def normalize_merchant(name: str) -> list[str]:
    lowered = name.lower()
    lowered = lowered.replace("*", " ")
    lowered = re.sub(r"[^\w\s]", " ", lowered)
    tokens = [t for t in lowered.split() if t and t not in _STOPWORDS]
    # Preserve order but unique for overlap.
    seen: list[str] = []
    for tok in tokens:
        if tok not in seen:
            seen.append(tok)
    return seen


def merchant_overlap(a: str, b: str) -> float:
    ta, tb = set(normalize_merchant(a)), set(normalize_merchant(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def compare_claim(
    extracted: ExtractedReceipt,
    claimed: ClaimedExpense | None,
    settings: Settings,
) -> tuple[Comparison, list[str]]:
    warnings: list[str] = []
    if claimed is None:
        return Comparison(performed=False), warnings

    receipt_total = field_value(extracted.total)
    receipt_currency = field_value(extracted.currency)
    receipt_date = field_value(extracted.date)
    receipt_merchant = field_value(extracted.merchant)

    claimed_currency = (claimed.currency or "USD").upper()
    receipt_currency_s = str(receipt_currency).upper() if receipt_currency else None

    amount_match: MatchResult
    if claimed.amount is None or receipt_total is None:
        amount_match = MatchResult(
            result="unknown",
            claimed=claimed.amount,
            receipt=receipt_total,
            diff=None,
        )
        if receipt_total is None:
            warnings.append("TOTAL_NOT_FOUND")
    elif receipt_currency_s and receipt_currency_s != claimed_currency:
        amount_match = MatchResult(
            result="unknown",
            claimed=claimed.amount,
            receipt=float(receipt_total),
            diff=None,
        )
        warnings.append("CURRENCY_DIFFERS")
    else:
        diff = abs(float(receipt_total) - float(claimed.amount))
        tolerance = max(
            settings.amount_tolerance_usd,
            abs(claimed.amount) * (settings.amount_tolerance_pct / 100.0),
        )
        matched = diff <= tolerance
        amount_match = MatchResult(
            result="match" if matched else "mismatch",
            claimed=claimed.amount,
            receipt=float(receipt_total),
            diff=round(float(receipt_total) - float(claimed.amount), 2),
        )
        if not matched:
            warnings.append("AMOUNT_MISMATCH")

    if extracted.total and extracted.total.confidence.value == "low" and receipt_total is not None:
        warnings.append("LOW_CONFIDENCE_TOTAL")

    date_match: MatchResult
    claimed_d = _parse_date(claimed.date)
    receipt_d = _parse_date(str(receipt_date) if receipt_date else None)
    if claimed.date is None or receipt_d is None or claimed_d is None:
        date_match = MatchResult(result="unknown", claimed=claimed.date, receipt=receipt_date)
    else:
        delta = abs((receipt_d - claimed_d).days)
        if delta == 0:
            date_match = MatchResult(result="match", claimed=claimed.date, receipt=str(receipt_date))
        elif delta == 1:
            date_match = MatchResult(result="match", claimed=claimed.date, receipt=str(receipt_date))
            warnings.append("DATE_OFF_BY_ONE_DAY")
        else:
            date_match = MatchResult(result="mismatch", claimed=claimed.date, receipt=str(receipt_date))
            warnings.append("DATE_MISMATCH")

    merchant_match: MatchResult
    if not claimed.merchant or not receipt_merchant:
        merchant_match = MatchResult(
            result="unknown",
            claimed=claimed.merchant,
            receipt=receipt_merchant,
        )
    else:
        overlap = merchant_overlap(str(claimed.merchant), str(receipt_merchant))
        matched = overlap >= 0.5
        merchant_match = MatchResult(
            result="match" if matched else "mismatch",
            claimed=claimed.merchant,
            receipt=receipt_merchant,
        )
        if not matched:
            warnings.append("MERCHANT_MISMATCH")

    alcohol_not_in_memo = None
    if extracted.alcohol_detected:
        memo = (claimed.memo or "").lower()
        mentioned = any(word in memo for word in _ALCOHOL_MEMO_WORDS)
        alcohol_not_in_memo = not mentioned
        if alcohol_not_in_memo:
            warnings.append("ALCOHOL_NOT_MENTIONED_IN_MEMO")

    return (
        Comparison(
            performed=True,
            amount_match=amount_match,
            date_match=date_match,
            merchant_match=merchant_match,
            alcohol_not_in_memo=alcohol_not_in_memo,
        ),
        warnings,
    )
