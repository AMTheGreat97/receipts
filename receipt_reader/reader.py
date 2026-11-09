from __future__ import annotations

import json
import time
from pathlib import Path

from receipt_reader.compare import compare_claim, field_value
from receipt_reader.config import Settings, load_settings
from receipt_reader.extractor import (
    LLMClient,
    OpenRouterClient,
    classify_document,
    extract_document,
)
from receipt_reader.loader import load_document
from receipt_reader.models import (
    ClaimedExpense,
    Comparison,
    ExtractedReceipt,
    ExtractMode,
    Meta,
    ReceiptResult,
    ReceiptStatus,
)
from receipt_reader.ocr import ocr_images
from receipt_reader.security import sanitize_payment_last4, screen_injection
from receipt_reader.summarize import build_summary, decide_status, found_and_missing


def _empty_meta(model: str, mode: ExtractMode, **kwargs) -> Meta:
    return Meta(model=model, mode=mode, **kwargs)


def _unsupported(path: Path, message: str, settings: Settings, mode: ExtractMode) -> ReceiptResult:
    return ReceiptResult(
        file=path.name,
        status=ReceiptStatus.unsupported_file,
        summary=message,
        message=message,
        meta=_empty_meta(settings.model if mode is ExtractMode.vision else settings.ocr_model, mode),
    )


def read_receipt(
    file_path: str | Path,
    claimed: ClaimedExpense | None = None,
    mode: ExtractMode | str = ExtractMode.vision,
    llm_client: LLMClient | None = None,
    settings: Settings | None = None,
) -> ReceiptResult:
    settings = settings or load_settings()
    mode = ExtractMode(mode) if not isinstance(mode, ExtractMode) else mode
    model = settings.ocr_model if mode is ExtractMode.ocr else settings.model
    path = Path(file_path)
    started = time.perf_counter()

    loaded = load_document(path, settings)
    if loaded.status is ReceiptStatus.unsupported_file:
        return _unsupported(path, loaded.message or "unsupported file", settings, mode)

    images = loaded.images
    ocr_text = None
    if mode is ExtractMode.ocr:
        try:
            ocr_text = ocr_images(images)
        except Exception as exc:  # pragma: no cover - engine import/runtime
            elapsed = int((time.perf_counter() - started) * 1000)
            return ReceiptResult(
                file=path.name,
                pages_processed=len(images),
                status=ReceiptStatus.error,
                summary=f"OCR failed: {exc}",
                message=str(exc),
                meta=_empty_meta(model, mode, latency_ms=elapsed),
            )

    vision_images = images[: settings.vision_max_pages]
    work_images = vision_images if mode is ExtractMode.vision else images

    client = llm_client
    if client is None:
        try:
            client = OpenRouterClient(settings)
        except RuntimeError as exc:
            elapsed = int((time.perf_counter() - started) * 1000)
            return ReceiptResult(
                file=path.name,
                pages_processed=len(work_images),
                status=ReceiptStatus.error,
                summary=str(exc),
                message=str(exc),
                meta=_empty_meta(model, mode, latency_ms=elapsed, ocr_text=ocr_text),
            )

    raw_bundle: dict = {}
    try:
        classify, classify_raw = classify_document(
            client,
            mode=mode,
            images=work_images,
            ocr_text=ocr_text,
            model=model,
        )
        raw_bundle["classify"] = classify_raw
    except Exception as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        return ReceiptResult(
            file=path.name,
            pages_processed=len(work_images),
            status=ReceiptStatus.error,
            summary=f"Classification failed: {exc}",
            message=str(exc),
            meta=_empty_meta(model, mode, latency_ms=elapsed, ocr_text=ocr_text),
        )

    warnings: list[str] = []
    if not classify.is_receipt:
        elapsed = int((time.perf_counter() - started) * 1000)
        warnings.append("NOT_A_RECEIPT")
        extracted = ExtractedReceipt(receipt_type=classify.receipt_type)
        found, missing = found_and_missing(extracted)
        return ReceiptResult(
            file=path.name,
            pages_processed=len(work_images),
            status=ReceiptStatus.unreadable,
            summary=build_summary(extracted, Comparison(performed=False), is_receipt=False),
            extracted=extracted,
            found=found,
            missing=missing,
            warnings=warnings,
            meta=_empty_meta(
                model,
                mode,
                latency_ms=elapsed,
                ocr_text=ocr_text,
                is_receipt=False,
                classify_reason=classify.reason,
                llm_raw_output=raw_bundle,
            ),
        )

    try:
        extracted, payload, extract_raw = extract_document(
            client,
            mode=mode,
            images=work_images,
            ocr_text=ocr_text,
            model=model,
        )
        raw_bundle["extract"] = payload
        raw_bundle["extract_raw"] = extract_raw
    except Exception as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        return ReceiptResult(
            file=path.name,
            pages_processed=len(work_images),
            status=ReceiptStatus.error,
            summary=f"Extraction failed after retry: {exc}",
            message=str(exc),
            warnings=warnings,
            meta=_empty_meta(
                model,
                mode,
                latency_ms=elapsed,
                ocr_text=ocr_text,
                is_receipt=True,
                classify_reason=classify.reason,
                llm_raw_output=raw_bundle,
            ),
        )

    if payload.get("unreadable"):
        warnings.append("NOT_A_RECEIPT")
        unreadable = True
    else:
        unreadable = False
    if payload.get("multiple_totals"):
        warnings.append("MULTIPLE_TOTALS")
    if payload.get("multi_receipt"):
        warnings.append("MULTI_RECEIPT")

    sanitize_payment_last4(extracted)
    extra_texts = [ocr_text or "", str(payload.get("injection_text") or "")]
    security = screen_injection(extracted, extra_texts)
    if security.injection_detected:
        warnings.append("PROMPT_INJECTION_IN_RECEIPT")

    comparison, compare_warnings = compare_claim(extracted, claimed, settings)
    warnings.extend(compare_warnings)

    found, missing = found_and_missing(extracted)
    if field_value(extracted.total) is None:
        if "TOTAL_NOT_FOUND" not in warnings:
            warnings.append("TOTAL_NOT_FOUND")

    status = decide_status(extracted, found, unreadable=unreadable, is_receipt=True)
    summary = build_summary(extracted, comparison, is_receipt=True)
    elapsed = int((time.perf_counter() - started) * 1000)
    return ReceiptResult(
        file=path.name,
        pages_processed=len(work_images),
        status=status,
        summary=summary,
        extracted=extracted,
        found=found,
        missing=missing,
        comparison=comparison,
        warnings=warnings,
        security=security,
        meta=_empty_meta(
            model,
            mode,
            latency_ms=elapsed,
            ocr_text=ocr_text,
            is_receipt=True,
            classify_reason=classify.reason,
            llm_raw_output=raw_bundle,
        ),
    )
