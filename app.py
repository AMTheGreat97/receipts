from __future__ import annotations

import json
from pathlib import Path

import gradio as gr

from receipt_reader.models import ClaimedExpense, ExtractMode
from receipt_reader.reader import read_receipt
from tests.make_fixtures import generate

FIXTURES = generate()


def _as_path(file_obj) -> str | None:
    if file_obj is None:
        return None
    if isinstance(file_obj, str):
        return file_obj
    if isinstance(file_obj, dict):
        return file_obj.get("path") or file_obj.get("name")
    return getattr(file_obj, "path", None) or getattr(file_obj, "name", None)


FIXTURE_CHOICES = {
    "Itemized restaurant": "itemized.png",
    "2-page PDF": "two_page.pdf",
    "EUR cafe": "eur.png",
    "Not a receipt": "non_receipt.png",
    "Injection phrase": "injection.png",
}


def analyze(file_obj, mode: str, claimed_json: str, fixture_name: str | None):
    path = _as_path(file_obj)
    if (not path) and fixture_name:
        key = FIXTURE_CHOICES.get(fixture_name)
        if key:
            path = str(FIXTURES[key])
    if not path:
        raise gr.Error("Upload a PDF or image, or pick a synthetic fixture.")
    claimed = None
    if claimed_json and claimed_json.strip():
        try:
            claimed = ClaimedExpense.model_validate(json.loads(claimed_json))
        except Exception as exc:
            raise gr.Error(f"Claimed JSON is invalid: {exc}") from exc
    result = read_receipt(path, claimed=claimed, mode=mode)
    status = result.status.value
    warn = ", ".join(result.warnings) or "none"
    found = ", ".join(result.found) or "none"
    missing = ", ".join(result.missing) or "none"
    classify = result.meta.classify_reason or ""
    is_receipt = result.meta.is_receipt
    markdown = f"""### Status: `{status}`
**{result.summary}**

- Classified as receipt: **{is_receipt}**
- Classifier reason: {classify or "(n/a)"}
- Mode: `{result.meta.mode.value}` · model: `{result.meta.model}` · {result.meta.latency_ms} ms · pages: {result.pages_processed}
- Found: {found}
- Missing: {missing}
- Warnings: {warn}
- Injection: {result.security.injection_detected}
"""
    payload = result.model_dump(mode="json")
    if payload.get("meta"):
        payload["meta"]["llm_raw_output"] = payload["meta"].get("llm_raw_output")
    return markdown, json.dumps(payload, indent=2), result.meta.ocr_text or "(vision mode has no OCR text)"


def load_example(name: str | None):
    if not name:
        return None
    key = FIXTURE_CHOICES[name]
    return str(FIXTURES[key])


with gr.Blocks(title="Receipt Reader POC") as demo:
    gr.Markdown(
        """
# Receipt Reader POC
Upload a PDF or image. The app **first checks whether it is a receipt**, then extracts merchant, date, totals, line items, alcohol, and payment last-4 with confidence.

**Two sources**
1. **Vision** — send the first 1–2 page images to an OpenRouter vision model.
2. **OCR → LLM** — RapidOCR the pages, then send that text to the model.
"""
    )
    with gr.Row():
        with gr.Column():
            file_in = gr.File(label="Receipt PDF or image", file_types=[".pdf", ".png", ".jpg", ".jpeg", ".webp"])
            mode = gr.Radio(
                choices=[ExtractMode.vision.value, ExtractMode.ocr.value],
                value=ExtractMode.vision.value,
                label="Extraction source",
            )
            claimed = gr.Textbox(
                label="Optional claimed expense JSON",
                placeholder='{"amount": 150, "currency": "USD", "date": "2026-06-25", "merchant": "Prime Cut", "memo": "team dinner"}',
                lines=4,
            )
            example = gr.Dropdown(
                choices=list(FIXTURE_CHOICES.keys()),
                value=None,
                label="Or load a synthetic fixture",
            )
            run = gr.Button("Extract", variant="primary")
        with gr.Column():
            summary = gr.Markdown()
            ocr_out = gr.Textbox(label="OCR text (OCR mode)", lines=12)
            json_out = gr.Code(label="Full JSON", language="json")

    example.change(load_example, inputs=example, outputs=file_in)
    run.click(analyze, inputs=[file_in, mode, claimed, example], outputs=[summary, json_out, ocr_out])


if __name__ == "__main__":
    print("Starting Gradio on http://127.0.0.1:7860 ...", flush=True)
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        inbrowser=False,
        show_error=True,
    )
