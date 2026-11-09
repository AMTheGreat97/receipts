from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from receipt_reader.config import MAX_FILE_BYTES, Settings
from receipt_reader.models import ReceiptStatus

RENDER_DPI = 200
MAX_SIDE_PX = 2000


@dataclass
class LoadedDocument:
    path: Path
    kind: str
    images: list[Image.Image]
    status: ReceiptStatus | None = None
    message: str | None = None


def detect_type(data: bytes) -> str:
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if len(data) > 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in {b"heic", b"heix", b"hevc", b"mif1", b"msf1"}:
            return "heic"
    return "unknown"


def _normalize(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    elif image.mode == "L":
        image = image.convert("RGB")
    w, h = image.size
    longest = max(w, h)
    if longest > MAX_SIDE_PX:
        scale = MAX_SIDE_PX / longest
        image = image.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
    return image


def _pdf_to_images(data: bytes, max_pages: int) -> tuple[list[Image.Image] | None, str | None, int]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    page_count = len(pdf)
    if page_count > max_pages:
        return None, f"PDF has {page_count} pages; max is {max_pages}", page_count
    images: list[Image.Image] = []
    scale = RENDER_DPI / 72
    for i in range(page_count):
        page = pdf[i]
        bitmap = page.render(scale=scale)
        pil = bitmap.to_pil()
        images.append(_normalize(pil))
    return images, None, page_count


def load_document(file_path: str | Path, settings: Settings) -> LoadedDocument:
    path = Path(file_path)
    if not path.exists():
        return LoadedDocument(
            path=path,
            kind="unknown",
            images=[],
            status=ReceiptStatus.unsupported_file,
            message=f"File not found: {path}",
        )
    data = path.read_bytes()
    if len(data) > MAX_FILE_BYTES:
        return LoadedDocument(
            path=path,
            kind="unknown",
            images=[],
            status=ReceiptStatus.unsupported_file,
            message=f"File is {len(data)} bytes; max is {MAX_FILE_BYTES}",
        )
    kind = detect_type(data)
    if kind == "pdf":
        images, err, _pages = _pdf_to_images(data, settings.max_pages)
        if err:
            return LoadedDocument(
                path=path,
                kind="pdf",
                images=[],
                status=ReceiptStatus.unsupported_file,
                message=err,
            )
        return LoadedDocument(path=path, kind="pdf", images=images or [])
    if kind in {"png", "jpeg", "webp"}:
        image = Image.open(BytesIO(data))
        return LoadedDocument(path=path, kind=kind, images=[_normalize(image)])
    if kind == "heic":
        return LoadedDocument(
            path=path,
            kind="heic",
            images=[],
            status=ReceiptStatus.unsupported_file,
            message="HEIC is not supported in this POC",
        )
    return LoadedDocument(
        path=path,
        kind=kind,
        images=[],
        status=ReceiptStatus.unsupported_file,
        message="Unsupported or corrupt file (magic bytes did not match PDF/PNG/JPEG/WEBP)",
    )
