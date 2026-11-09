# Receipt Reader POC design (2026-11-09)

Build-from-scratch Python module + Gradio, matching `reciept_analyser/RECEIPT_READER_SPEC.md`, with two extraction sources.

## Decision

Do **not** fork `receipt-ocr` or `open-receipt-extractor`. Reuse RapidOCR as the OCR primitive. All structured extraction goes through OpenRouter so the schema, confidence, comparison, and security rules stay in this repo.

## Flow

1. Detect file type by magic bytes; reject >15 MB and PDFs over `RECEIPT_MAX_PAGES`.
2. PDF → images at 200 DPI via pypdfium2; downscale longest side to 2000 px.
3. **Classify** with OpenRouter: is this a receipt?
4. If yes, **extract** JSON (merchant, date, totals, tax, tip, last-4, line items, alcohol, receipt type).
5. Deterministic layers: card truncation, injection phrase screen, claim comparison, found/missing, one-line summary.

## Modes

- `vision`: classify + extract with the first `RECEIPT_VISION_MAX_PAGES` (default 2) page images.
- `ocr`: RapidOCR all loaded pages, then classify + extract from that text.

## Surfaces

- `read_receipt(path, claimed=None, mode="vision")`
- `python -m receipt_reader`
- `python app.py` Gradio UI
