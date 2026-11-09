from __future__ import annotations

import argparse
import json
from pathlib import Path

from receipt_reader.models import ClaimedExpense, ExtractMode
from receipt_reader.reader import read_receipt


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extract structured data from a receipt PDF or image.")
    parser.add_argument("file", help="Path to a PDF or image")
    parser.add_argument("--claimed", help="Path to ClaimedExpense JSON")
    parser.add_argument("--json", action="store_true", dest="json_only", help="Print raw JSON only")
    parser.add_argument(
        "--mode",
        choices=[m.value for m in ExtractMode],
        default=ExtractMode.vision.value,
        help="vision = first pages as images; ocr = RapidOCR text then LLM",
    )
    args = parser.parse_args(argv)

    claimed = None
    if args.claimed:
        payload = json.loads(Path(args.claimed).read_text(encoding="utf-8"))
        claimed = ClaimedExpense.model_validate(payload)

    result = read_receipt(args.file, claimed=claimed, mode=args.mode)
    dumped = result.model_dump(mode="json")
    if args.json_only:
        print(json.dumps(dumped, indent=2))
        return

    print(result.summary)
    print()
    print("Found:", ", ".join(result.found) or "(none)")
    print("Missing:", ", ".join(result.missing) or "(none)")
    print("Warnings:", ", ".join(result.warnings) or "(none)")
    print()
    print(json.dumps(dumped, indent=2))
