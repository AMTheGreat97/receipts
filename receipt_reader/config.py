from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")
load_dotenv()

DEFAULT_MODEL = "openai/gpt-4o-mini"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_FILE_BYTES = 15 * 1024 * 1024


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str
    ocr_model: str
    base_url: str
    max_pages: int
    vision_max_pages: int
    amount_tolerance_usd: float
    amount_tolerance_pct: float


def load_settings() -> Settings:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    model = os.getenv("RECEIPT_MODEL", "").strip() or DEFAULT_MODEL
    ocr_model = os.getenv("RECEIPT_OCR_MODEL", "").strip() or model
    base_url = os.getenv("OPENROUTER_BASE_URL", "").strip() or OPENROUTER_BASE_URL
    return Settings(
        api_key=key,
        model=model,
        ocr_model=ocr_model,
        base_url=base_url,
        max_pages=int(os.getenv("RECEIPT_MAX_PAGES", "5")),
        vision_max_pages=int(os.getenv("RECEIPT_VISION_MAX_PAGES", "2")),
        amount_tolerance_usd=float(os.getenv("RECEIPT_AMOUNT_TOLERANCE_USD", "1.00")),
        amount_tolerance_pct=float(os.getenv("RECEIPT_AMOUNT_TOLERANCE_PCT", "2")),
    )
