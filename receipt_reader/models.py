from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ReceiptStatus(str, Enum):
    ok = "ok"
    partial = "partial"
    unreadable = "unreadable"
    unsupported_file = "unsupported_file"
    error = "error"


class ReceiptType(str, Enum):
    itemized = "itemized"
    summary_only = "summary_only"
    card_slip = "card_slip"
    invoice = "invoice"
    unknown = "unknown"


class ExtractMode(str, Enum):
    vision = "vision"
    ocr = "ocr"


class ClaimedExpense(BaseModel):
    amount: float | None = None
    currency: str | None = "USD"
    date: str | None = None
    merchant: str | None = None
    category: str | None = None
    memo: str | None = None


class ExtractedField(BaseModel):
    value: Any = None
    confidence: Confidence = Confidence.low
    raw_text: str | None = None


class LineItem(BaseModel):
    description: str
    quantity: float | None = None
    amount: float | None = None
    is_alcohol: bool = False


class ExtractedReceipt(BaseModel):
    merchant: ExtractedField | None = None
    date: ExtractedField | None = None
    total: ExtractedField | None = None
    currency: ExtractedField | None = None
    subtotal: ExtractedField | None = None
    tax: ExtractedField | None = None
    tip: ExtractedField | None = None
    payment_last4: ExtractedField | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    alcohol_detected: bool = False
    receipt_type: ReceiptType = ReceiptType.unknown


class MatchResult(BaseModel):
    result: Literal["match", "mismatch", "unknown"]
    claimed: Any = None
    receipt: Any = None
    diff: float | None = None


class Comparison(BaseModel):
    performed: bool = False
    amount_match: MatchResult | None = None
    date_match: MatchResult | None = None
    merchant_match: MatchResult | None = None
    alcohol_not_in_memo: bool | None = None


class SecurityResult(BaseModel):
    injection_detected: bool = False
    evidence: str | None = None


class Meta(BaseModel):
    model: str
    prompt_version: str = "extract_v1"
    latency_ms: int = 0
    mode: ExtractMode = ExtractMode.vision
    ocr_text: str | None = None
    is_receipt: bool | None = None
    classify_reason: str | None = None
    llm_raw_output: dict[str, Any] | None = None


class ReceiptResult(BaseModel):
    file: str
    pages_processed: int = 0
    status: ReceiptStatus
    summary: str = ""
    extracted: ExtractedReceipt = Field(default_factory=ExtractedReceipt)
    found: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    comparison: Comparison = Field(default_factory=Comparison)
    warnings: list[str] = Field(default_factory=list)
    security: SecurityResult = Field(default_factory=SecurityResult)
    meta: Meta
    message: str | None = None


class ClassifyResult(BaseModel):
    is_receipt: bool
    confidence: Confidence = Confidence.medium
    reason: str = ""
    receipt_type: ReceiptType = ReceiptType.unknown
