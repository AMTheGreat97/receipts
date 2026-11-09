from __future__ import annotations

import base64
import io
import json
import re
from typing import Any, Protocol

from pathlib import Path

from openai import OpenAI
from PIL import Image

from receipt_reader.config import Settings
from receipt_reader.models import (
    ClassifyResult,
    Confidence,
    ExtractedField,
    ExtractedReceipt,
    ExtractMode,
    LineItem,
    ReceiptType,
)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


class LLMClient(Protocol):
    def complete(self, messages: list[dict[str, Any]], model: str) -> str: ...


class OpenRouterClient:
    def __init__(self, settings: Settings):
        if not settings.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set. Copy .env.example to .env.")
        self._client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            default_headers={
                "HTTP-Referer": "https://localhost",
                "X-Title": "receipt-reader-poc",
            },
        )

    def complete(self, messages: list[dict[str, Any]], model: str) -> str:
        response = self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"},
            timeout=90,
        )
        return response.choices[0].message.content or ""


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def image_to_data_url(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def parse_json_content(text: str) -> dict[str, Any]:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.S)
    if fenced:
        stripped = fenced.group(1)
    return json.loads(stripped)


def _confidence(value: object) -> Confidence:
    try:
        return Confidence(str(value).lower())
    except ValueError:
        return Confidence.low


def _field(payload: dict[str, Any] | None) -> ExtractedField | None:
    if not payload or not isinstance(payload, dict):
        return None
    return ExtractedField(
        value=payload.get("value"),
        confidence=_confidence(payload.get("confidence", "low")),
        raw_text=payload.get("raw_text"),
    )


def extracted_from_payload(data: dict[str, Any]) -> ExtractedReceipt:
    items = []
    for raw in data.get("line_items") or []:
        if not isinstance(raw, dict):
            continue
        desc = str(raw.get("description") or "").strip()
        if not desc:
            continue
        items.append(
            LineItem(
                description=desc,
                quantity=raw.get("quantity"),
                amount=raw.get("amount"),
                is_alcohol=bool(raw.get("is_alcohol")),
            )
        )
    try:
        rtype = ReceiptType(str(data.get("receipt_type") or "unknown"))
    except ValueError:
        rtype = ReceiptType.unknown
    alcohol = bool(data.get("alcohol_detected")) or any(i.is_alcohol for i in items)
    return ExtractedReceipt(
        merchant=_field(data.get("merchant")),
        date=_field(data.get("date")),
        total=_field(data.get("total")),
        currency=_field(data.get("currency")),
        subtotal=_field(data.get("subtotal")),
        tax=_field(data.get("tax")),
        tip=_field(data.get("tip")),
        payment_last4=_field(data.get("payment_last4")),
        line_items=items,
        alcohol_detected=alcohol,
        receipt_type=rtype,
    )


def classify_from_payload(data: dict[str, Any]) -> ClassifyResult:
    try:
        rtype = ReceiptType(str(data.get("receipt_type") or "unknown"))
    except ValueError:
        rtype = ReceiptType.unknown
    return ClassifyResult(
        is_receipt=bool(data.get("is_receipt")),
        confidence=_confidence(data.get("confidence", "medium")),
        reason=str(data.get("reason") or ""),
        receipt_type=rtype,
    )


def _vision_user_content(prompt: str, images: list[Image.Image]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for image in images:
        content.append({"type": "image_url", "image_url": {"url": image_to_data_url(image)}})
    return content


def _call_json(
    client: LLMClient,
    *,
    system: str,
    user_content: str | list[dict[str, Any]],
    model: str,
) -> tuple[dict[str, Any], str]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    raw = client.complete(messages, model)
    try:
        return parse_json_content(raw), raw
    except (json.JSONDecodeError, ValueError):
        retry_messages = messages + [
            {
                "role": "user",
                "content": "Return only valid JSON matching the schema. No markdown, no commentary.",
            }
        ]
        raw = client.complete(retry_messages, model)
        return parse_json_content(raw), raw


def classify_document(
    client: LLMClient,
    *,
    mode: ExtractMode,
    images: list[Image.Image],
    ocr_text: str | None,
    model: str,
) -> tuple[ClassifyResult, str]:
    system = load_prompt("classify_v1.txt")
    if mode is ExtractMode.ocr:
        user: str | list[dict[str, Any]] = (
            "OCR text from the uploaded file follows. Classify it.\n\n" + (ocr_text or "")
        )
    else:
        user = _vision_user_content("Classify the attached page image(s).", images)
    data, raw = _call_json(client, system=system, user_content=user, model=model)
    return classify_from_payload(data), raw


def extract_document(
    client: LLMClient,
    *,
    mode: ExtractMode,
    images: list[Image.Image],
    ocr_text: str | None,
    model: str,
) -> tuple[ExtractedReceipt, dict[str, Any], str]:
    system = load_prompt("extract_v1.txt")
    if mode is ExtractMode.ocr:
        user: str | list[dict[str, Any]] = (
            "OCR text from the receipt follows. Extract every field you can.\n\n" + (ocr_text or "")
        )
    else:
        user = _vision_user_content(
            "Extract every field you can from the attached receipt page image(s), in order.",
            images,
        )
    data, raw = _call_json(client, system=system, user_content=user, model=model)
    return extracted_from_payload(data), data, raw
