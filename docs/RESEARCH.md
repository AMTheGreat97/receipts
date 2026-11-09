# Receipt extraction libraries (Nov 2026)

We **build our own** module against `RECEIPT_READER_SPEC.md` and reuse an OCR engine. Nothing off the shelf matches OpenRouter + per-field confidence + claim comparison + injection screening + Gradio dual-mode.

## Closest open-source

| Library | What it does | Why not fork |
|---|---|---|
| [receipt-ocr](https://github.com/bhimrazy/receipt-ocr) (`pip install receipt-ocr`) | Tesseract OCR **or** vision-LLM → JSON. OpenAI-compatible client. ~750 stars. | Schema is merchant/date/total/line_items only. No confidence, claim compare, alcohol, security screen, or Gradio. Pins OpenAI env names, not OpenRouter. Tesseract is a system dependency. |
| [open-receipt-extractor](https://pypi.org/project/open-receipt-extractor/) | OCR + layout reconstruction + regex/parser JSON. EasyOCR adapter. | No LLM/vision path. Python 3.12+. Canadian-tax oriented. |
| [docpick](https://github.com/QuartzUnit/docpick) | Local OCR + local LLM, Pydantic schemas including `receipt`. | Local-only; not OpenRouter. |
| [docket](https://github.com/KazKozDev/docket) / [invocr](https://github.com/fin-officer/invocr) | Invoice/receipt pipelines with Tesseract/EasyOCR + LLM. | Different output contract; heavier than a POC. |

## Commercial (not used)

Mindee Receipt, Veryfi, Taggun, Amazon Textract AnalyzeExpense, Google Document AI Receipt parser, Azure Receipts. These are hosted APIs, not OpenRouter.

## Research models (not used)

NAVER Donut, LayoutLMv3 — need fine-tuning and local GPU; they do not speak our JSON contract.

## What we reuse

- **RapidOCR** (`pip install rapidocr onnxruntime`) as the OCR primitive. No Tesseract install. Works on Windows.
- **pypdfium2 + Pillow** for PDF→image and normalization (as specified).
- **OpenAI Python SDK** pointed at `https://openrouter.ai/api/v1`.
