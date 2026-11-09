# Receipt Reader POC Implementation Plan

> **For agentic workers:** Implement in this session. Dual extraction modes + Gradio, matching `reciept_analyser/RECEIPT_READER_SPEC.md`.

**Goal:** A standalone Python receipt reader that classifies an upload as a receipt, then extracts structured fields with confidence via either RapidOCR+LLM or vision-LLM (first two pages), with a Gradio UI and CLI.

**Architecture:** Load PDF/image → optional RapidOCR → OpenRouter classify (`is_receipt`) → OpenRouter extract JSON → deterministic compare/summarize/security. No existing receipt library is forked; RapidOCR is the OCR primitive only.

**Tech Stack:** Python 3.10+, pydantic v2, pypdfium2, Pillow, RapidOCR+onnxruntime, OpenAI SDK → OpenRouter, Gradio, pytest.

## Global Constraints

- LLM only through OpenRouter (`https://openrouter.ai/api/v1`). Never hard-code a provider SDK beyond the OpenAI-compatible client.
- Default vision model: `openai/gpt-4o-mini`. Override with `RECEIPT_MODEL`. OCR text model: `RECEIPT_OCR_MODEL` (falls back to `RECEIPT_MODEL`).
- PDF render ~200 DPI via pypdfium2; longest image side ≤ 2000 px.
- Reject files > 15 MB or PDFs with more than `RECEIPT_MAX_PAGES` (default 5) pages.
- Vision mode sends at most `RECEIPT_VISION_MAX_PAGES` pages (default 2).
- `OPENROUTER_API_KEY` lives only in `.env` (gitignored).
- Do not approve/reject expenses; report facts only.
- Temperature 0; invalid JSON retried once; `payment_last4` only.

## Files

- Create: `receipt_reader/{__init__,__main__,config,models,loader,ocr,extractor,compare,summarize,security,cli,reader}.py`
- Create: `receipt_reader/prompts/{classify_v1,extract_v1}.txt`
- Create: `tests/{conftest,make_fixtures,test_loader,test_compare,test_summarize,test_security,test_extractor_mocked}.py`
- Create: `app.py`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md`

## Tasks

1. Scaffold + models
2. compare / summarize / security (unit tests first)
3. loader + synthetic fixtures
4. extractor (mocked LLM) with vision vs OCR modes
5. reader orchestration, CLI, Gradio
6. pytest, live smoke, Gradio browser check
