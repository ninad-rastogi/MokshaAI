from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from chat.rag.loader import ScriptureDocumentLoader
from chat.rag.ocr import OcrUnavailableError, TesseractOcrEngine


class FakeDocument(list):
    def close(self) -> None:
        return None


def test_tesseract_ocr_reports_missing_binary(tmp_path: Path) -> None:
    engine = TesseractOcrEngine(command=str(tmp_path / "missing-tesseract.exe"))

    with pytest.raises(OcrUnavailableError, match="ocr_tesseract_missing"):
        engine.assert_available()


def test_loader_uses_configured_ocr_engine_when_forced(tmp_path: Path) -> None:
    pdf_path = tmp_path / "volume.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    fake_page = Mock()
    fake_document = FakeDocument([fake_page])
    fake_engine = Mock()
    fake_engine.cached_ocr_page.return_value = "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।"

    with (
        patch("chat.rag.loader.fitz.open", return_value=fake_document),
        patch("chat.rag.loader.configured_ocr_engine", return_value=fake_engine),
    ):
        chunks = ScriptureDocumentLoader(docs_dir=tmp_path)._load_pdf(
            pdf_path,
            "Open Wisdom",
            tmp_path,
            force_ocr=True,
        )

    fake_engine.cached_ocr_page.assert_called_once_with(fake_page, pdf_path, 1)
    assert chunks
    assert chunks[0]["scripture"] == "Open Wisdom"
    assert chunks[0]["file_name"] == "volume.pdf"
    assert chunks[0]["page"] == 1
    assert "कर्मण्येवाधिकारस्ते" in chunks[0]["text"]


def test_tesseract_ocr_uses_resumable_page_cache(settings, tmp_path: Path) -> None:
    settings.OCR_CACHE_DIR = tmp_path / "ocr-cache"
    pdf_path = tmp_path / "volume.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    page = Mock()
    engine = TesseractOcrEngine(command=str(tmp_path / "missing.exe"))

    with patch.object(engine, "ocr_page", return_value="cached text") as ocr_page:
        assert engine.cached_ocr_page(page, pdf_path, 1) == "cached text"
        assert engine.cached_ocr_page(page, pdf_path, 1) == "cached text"

    ocr_page.assert_called_once_with(page)
