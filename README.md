# Receipt Reader POC

Standalone module that reads an expense receipt (PDF or image), checks that it is actually a receipt, then extracts structured fields with confidence. Built against `reciept_analyser/RECEIPT_READER_SPEC.md`.

It does **not** approve or reject expenses. It reports facts.

## Library research: reuse or build?

Existing tools already do *some* of this work. None of them match this spec (OpenRouter, per-field confidence, claim comparison, injection screening, Gradio dual-mode), so **this POC is built from scratch**. The OCR engine is reused; the product is not forked.

Closest open-source:

- **[receipt-ocr](https://github.com/bhimrazy/receipt-ocr)** — Tesseract **or** a vision LLM → JSON. OpenAI-compatible. Closest overall. Different schema, no confidence/compare/security, OpenAI env names, Tesseract system install.
- **[open-receipt-extractor](https://pypi.org/project/open-receipt-extractor/)** — OCR + layout + parser JSON. No LLM.
- **docpick / docket / invocr** — local OCR+LLM document pipelines, not OpenRouter.

Commercial APIs (Mindee, Veryfi, Textract AnalyzeExpense, Google Document AI, Azure Receipts) are hosted products, not something to point at OpenRouter.

What we reuse: **RapidOCR** (`rapidocr` + `onnxruntime`) for the OCR path, **pypdfium2** + **Pillow** for PDF→image, **OpenAI SDK** pointed at `https://openrouter.ai/api/v1`.

Details: `docs/RESEARCH.md`.

## Two extraction sources

| Mode | What is sent to the model |
|---|---|
| `vision` (default) | JPEG of the first 1–2 pages |
| `ocr` | RapidOCR text of the loaded pages, then a text LLM call |

Both modes **classify first** (`is_receipt`). If it is not a receipt, extraction is skipped (`status: unreadable`, warning `NOT_A_RECEIPT`).

## Setup

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# put OPENROUTER_API_KEY in .env
python tests/make_fixtures.py
```

Environment:

| Variable | Default |
|---|---|
| `OPENROUTER_API_KEY` | required for live calls |
| `RECEIPT_MODEL` | `openai/gpt-4o-mini` |
| `RECEIPT_OCR_MODEL` | same as `RECEIPT_MODEL` |
| `RECEIPT_MAX_PAGES` | `5` |
| `RECEIPT_VISION_MAX_PAGES` | `2` |
| `RECEIPT_AMOUNT_TOLERANCE_USD` | `1.00` |
| `RECEIPT_AMOUNT_TOLERANCE_PCT` | `2` |

## CLI

```powershell
python -m receipt_reader tests/fixtures/itemized.png
python -m receipt_reader tests/fixtures/itemized.png --mode ocr
python -m receipt_reader tests/fixtures/itemized.png --json
python -m receipt_reader tests/fixtures/eur.png --claimed claimed.json
```

Default printout: one-line summary, found/missing/warnings, then full JSON.

## Gradio

```powershell
python app.py
```

Upload a PDF/image, pick **vision** or **ocr**, optionally paste a claimed-expense JSON, extract.

## Python

```python
from receipt_reader import read_receipt, ClaimedExpense

result = read_receipt("receipt.pdf", claimed=ClaimedExpense(amount=150, merchant="Prime Cut"))
print(result.summary, result.status, result.extracted.total)
```

## Tests

Unit tests mock OpenRouter. No network required:

```powershell
pytest -q
```

Live smoke (uses the key, skipped otherwise):

```powershell
pytest -q -k live --run-live
```

## Output

See the schema in `reciept_analyser/RECEIPT_READER_SPEC.md` §5. Every extracted field has `value` + `confidence` (`high`/`medium`/`low`). `summary` is built in code, not by the model.
