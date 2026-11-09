from __future__ import annotations

from receipt_reader.compare import field_value
from receipt_reader.models import (
    Comparison,
    ExtractedField,
    ExtractedReceipt,
    ReceiptStatus,
    ReceiptType,
)

CORE_FIELDS = ("merchant", "date", "total", "currency")


def _money(value: object | None) -> str | None:
    if isinstance(value, (int, float)):
        return f"${value:.2f}"
    return None


def _field_present(field: ExtractedField | None) -> bool:
    if field is None:
        return False
    if field.value is None or field.value == "":
        return False
    return True


def found_and_missing(extracted: ExtractedReceipt) -> tuple[list[str], list[str]]:
    found: list[str] = []
    for name in (*CORE_FIELDS, "subtotal", "tax", "tip", "payment_last4"):
        if _field_present(getattr(extracted, name)):
            found.append(name)
    if extracted.line_items:
        found.append("line_items")

    missing: list[str] = [name for name in CORE_FIELDS if name not in found]
    rtype = extracted.receipt_type
    expects_lines = rtype in (ReceiptType.itemized, ReceiptType.invoice)
    if expects_lines and "line_items" not in found:
        missing.append("line_items")
    if rtype in (ReceiptType.itemized, ReceiptType.invoice):
        for optional in ("tax", "tip", "payment_last4"):
            if optional not in found:
                missing.append(optional)
    return found, missing


def decide_status(
    extracted: ExtractedReceipt,
    found: list[str],
    *,
    unreadable: bool = False,
    is_receipt: bool | None = True,
) -> ReceiptStatus:
    if unreadable or is_receipt is False:
        return ReceiptStatus.unreadable
    core_ok = True
    for name in CORE_FIELDS:
        field: ExtractedField | None = getattr(extracted, name)
        if not _field_present(field):
            core_ok = False
            break
        if field.confidence.value == "low":
            core_ok = False
            break
    return ReceiptStatus.ok if core_ok else ReceiptStatus.partial


def build_summary(
    extracted: ExtractedReceipt,
    comparison: Comparison,
    *,
    is_receipt: bool | None = True,
) -> str:
    if is_receipt is False:
        return "Not a receipt; no extraction performed."

    merchant = field_value(extracted.merchant) or "merchant unknown"
    date_s = field_value(extracted.date) or "date unknown"
    total = field_value(extracted.total)
    currency = field_value(extracted.currency) or "currency unknown"
    total_s = _money(total)
    total_part = f"total {total_s} {currency}" if total_s else "total unknown"

    extras: list[str] = []
    tax_s = _money(field_value(extracted.tax))
    tip_s = _money(field_value(extracted.tip))
    if tax_s:
        extras.append(f"{tax_s} tax")
    if tip_s:
        extras.append(f"{tip_s} tip")
    extra_part = f" (incl. {', '.join(extras)})" if extras else ""

    alcohol_count = sum(1 for item in extracted.line_items if item.is_alcohol)
    if extracted.alcohol_detected or alcohol_count:
        n = alcohol_count or 1
        alcohol_note = f"{n} alcohol item" if n == 1 else f"{n} alcohol items"
    else:
        alcohol_note = "no alcohol"

    if not comparison.performed:
        compare_note = "no claim to compare"
    elif comparison.amount_match and comparison.amount_match.result == "match":
        compare_note = "matches claimed amount"
    elif comparison.amount_match and comparison.amount_match.result == "mismatch":
        compare_note = "amount mismatch"
    elif comparison.amount_match and comparison.amount_match.result == "unknown":
        compare_note = "claim comparison incomplete"
    else:
        compare_note = "no claim to compare"

    line = f"{merchant}, {date_s}, {total_part}{extra_part}; {alcohol_note}; {compare_note}."
    if len(line) > 200:
        line = line[:197] + "..."
    return line
