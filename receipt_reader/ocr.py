from __future__ import annotations

from PIL import Image

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr import RapidOCR

        _engine = RapidOCR()
    return _engine


def ocr_images(images: list[Image.Image]) -> str:
    """Run RapidOCR on each page and return concatenated text with page markers."""
    engine = _get_engine()
    chunks: list[str] = []
    for i, image in enumerate(images, start=1):
        result = engine(image)
        lines = _lines_from_result(result)
        header = f"--- page {i} ---"
        body = "\n".join(lines).strip()
        chunks.append(f"{header}\n{body}" if body else header)
    return "\n\n".join(chunks).strip()


def _lines_from_result(result) -> list[str]:
    if result is None:
        return []
    txts = getattr(result, "txts", None)
    if txts:
        return [str(t) for t in txts if t]
    # Older rapidocr_onnxruntime: (result_list, elapse)
    if isinstance(result, tuple) and result and isinstance(result[0], list):
        lines = []
        for row in result[0]:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                lines.append(str(row[1]))
        return lines
    if isinstance(result, list):
        lines = []
        for row in result:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                lines.append(str(row[1]))
        return lines
    return []
