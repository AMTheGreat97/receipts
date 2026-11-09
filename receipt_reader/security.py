from __future__ import annotations

import re

from receipt_reader.models import ExtractedReceipt, SecurityResult

_INJECTION_PATTERNS = [
    re.compile(r"\bauto-?approve\b", re.I),
    re.compile(r"\bpre-?approved\b", re.I),
    re.compile(r"\bapprove this\b", re.I),
    re.compile(r"\bapprove\b", re.I),
    re.compile(r"\bignore\b", re.I),
    re.compile(r"\boverride\b", re.I),
    re.compile(r"\bas an ai\b", re.I),
    re.compile(r"\bsystem\s*:", re.I),
]


def truncate_card(value: object | None) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        return None
    return digits[-4:]


def sanitize_payment_last4(extracted: ExtractedReceipt) -> None:
    if extracted.payment_last4 and extracted.payment_last4.value is not None:
        extracted.payment_last4.value = truncate_card(extracted.payment_last4.value)


def _collect_strings(extracted: ExtractedReceipt) -> list[str]:
    blobs: list[str] = []
    for name in (
        "merchant",
        "date",
        "total",
        "currency",
        "subtotal",
        "tax",
        "tip",
        "payment_last4",
    ):
        field = getattr(extracted, name)
        if field is None:
            continue
        if field.value is not None:
            blobs.append(str(field.value))
        if field.raw_text:
            blobs.append(field.raw_text)
    for item in extracted.line_items:
        blobs.append(item.description)
    return blobs


def screen_injection(extracted: ExtractedReceipt, extra_texts: list[str] | None = None) -> SecurityResult:
    texts = _collect_strings(extracted)
    if extra_texts:
        texts.extend(extra_texts)
    for text in texts:
        for pattern in _INJECTION_PATTERNS:
            match = pattern.search(text)
            if match:
                start = max(0, match.start() - 40)
                end = min(len(text), match.end() + 40)
                quote = text[start:end].strip()
                return SecurityResult(injection_detected=True, evidence=quote)
    return SecurityResult(injection_detected=False, evidence=None)
