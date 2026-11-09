from __future__ import annotations

from pathlib import Path

from receipt_reader.config import MAX_FILE_BYTES, Settings
from receipt_reader.loader import detect_type, load_document
from receipt_reader.models import ReceiptStatus

SETTINGS = Settings(
    api_key="test",
    model="test",
    ocr_model="test",
    base_url="https://openrouter.ai/api/v1",
    max_pages=5,
    vision_max_pages=2,
    amount_tolerance_usd=1.0,
    amount_tolerance_pct=2.0,
)


def test_magic_bytes_not_extension(tmp_path: Path, fixtures: dict[str, Path]):
    png = fixtures["itemized.png"].read_bytes()
    disguised = tmp_path / "receipt.txt"
    disguised.write_bytes(png)
    assert detect_type(png) == "png"
    loaded = load_document(disguised, SETTINGS)
    assert loaded.status is None
    assert loaded.kind == "png"
    assert len(loaded.images) == 1


def test_pdf_to_images_two_pages(fixtures: dict[str, Path]):
    loaded = load_document(fixtures["two_page.pdf"], SETTINGS)
    assert loaded.kind == "pdf"
    assert len(loaded.images) == 2
    for image in loaded.images:
        assert max(image.size) <= 2000


def test_page_limit_rejects_long_pdf(tmp_path: Path):
    from PIL import Image

    pages = [Image.new("RGB", (200, 200), "white") for _ in range(6)]
    path = tmp_path / "long.pdf"
    pages[0].save(path, "PDF", save_all=True, append_images=pages[1:])
    loaded = load_document(path, SETTINGS)
    assert loaded.status is ReceiptStatus.unsupported_file
    assert "pages" in (loaded.message or "").lower()


def test_size_limit(tmp_path: Path):
    path = tmp_path / "huge.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * (MAX_FILE_BYTES + 10))
    loaded = load_document(path, SETTINGS)
    assert loaded.status is ReceiptStatus.unsupported_file


def test_unknown_bytes(tmp_path: Path):
    path = tmp_path / "nope.bin"
    path.write_bytes(b"not-a-file")
    loaded = load_document(path, SETTINGS)
    assert loaded.status is ReceiptStatus.unsupported_file
