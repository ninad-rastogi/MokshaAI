"""Local OCR helpers for scripture PDFs."""

import hashlib
import logging
import os
import subprocess
import tempfile
import time
from contextlib import suppress
from pathlib import Path

import fitz
from django.conf import settings

logger = logging.getLogger("chat.rag.ocr")


class OcrUnavailableError(RuntimeError):
    """Raised when local OCR is configured but not usable."""


class TesseractOcrEngine:
    """CPU-safe OCR adapter for rasterized PDF pages."""

    def __init__(
        self,
        command: str | None = None,
        languages: str | None = None,
        tessdata_prefix: str | None = None,
        dpi: int | None = None,
        page_timeout_seconds: int | None = None,
        page_segmentation_mode: int | None = None,
    ) -> None:
        self.command = command or settings.SCRIPTURE_OCR_TESSERACT_CMD
        self.requested_languages = languages or settings.SCRIPTURE_OCR_LANGUAGES
        self.tessdata_prefix = (
            tessdata_prefix
            if tessdata_prefix is not None
            else settings.SCRIPTURE_OCR_TESSDATA_PREFIX
        )
        self.dpi = dpi or settings.SCRIPTURE_OCR_DPI
        self.page_timeout_seconds = (
            page_timeout_seconds or settings.SCRIPTURE_OCR_PAGE_TIMEOUT_SECONDS
        )
        self.page_segmentation_mode = (
            page_segmentation_mode or settings.SCRIPTURE_OCR_PSM
        )

    @property
    def name(self) -> str:
        return "tesseract"

    @property
    def languages(self) -> str:
        return self.requested_languages

    def assert_available(self) -> None:
        if not Path(self.command).exists():
            raise OcrUnavailableError("ocr_tesseract_missing")
        installed = self._installed_languages()
        requested = [lang for lang in self.requested_languages.split("+") if lang]
        missing = sorted(set(requested).difference(installed))
        if missing:
            raise OcrUnavailableError("ocr_language_data_missing")

    def ocr_page(self, page: fitz.Page) -> str:
        self.assert_available()
        scale = self.dpi / 72
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        image_handle, raw_image_path = tempfile.mkstemp(suffix=".png")
        os.close(image_handle)
        image_path = Path(raw_image_path)
        pixmap.save(str(image_path))
        try:
            return self._run_tesseract(image_path).strip()
        finally:
            with suppress(FileNotFoundError):
                image_path.unlink()

    def cached_ocr_page(self, page: fitz.Page, pdf_path: Path, page_number: int) -> str:
        """OCR one page with a resumable local text cache."""
        cache_file = self._page_cache_file(pdf_path, page_number)
        for attempt in range(3):
            try:
                if cache_file.exists():
                    return cache_file.read_text(encoding="utf-8")
                break
            except PermissionError:
                if attempt == 2:
                    raise
                time.sleep(0.2 * (attempt + 1))
        text = self.ocr_page(page)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = cache_file.with_name(f"{cache_file.name}.{os.getpid()}.tmp")
        for attempt in range(3):
            try:
                temp_file.write_text(text, encoding="utf-8")
                temp_file.replace(cache_file)
                break
            except PermissionError:
                if attempt == 2:
                    raise
                time.sleep(0.2 * (attempt + 1))
        return text

    def _installed_languages(self) -> set[str]:
        env = self._env()
        result = subprocess.run(
            [self.command, "--list-langs"],
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=30,
        )
        if result.returncode != 0:
            raise OcrUnavailableError("ocr_tesseract_unusable")
        return {
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip() and not line.lower().startswith("list of available")
        }

    def _run_tesseract(self, image_path: Path) -> str:
        result = subprocess.run(
            [
                self.command,
                str(image_path),
                "stdout",
                "-l",
                self.requested_languages,
                "--psm",
                str(self.page_segmentation_mode),
            ],
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=self._env(),
            timeout=self.page_timeout_seconds,
        )
        if result.returncode != 0:
            raise OcrUnavailableError("ocr_page_failed")
        return result.stdout

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        if self.tessdata_prefix:
            env["TESSDATA_PREFIX"] = self.tessdata_prefix
        return env

    def _page_cache_file(self, pdf_path: Path, page_number: int) -> Path:
        stat = pdf_path.stat()
        key = "|".join(
            [
                str(pdf_path.resolve()),
                str(stat.st_size),
                str(stat.st_mtime_ns),
                self.requested_languages,
                str(self.dpi),
                str(self.page_segmentation_mode),
                self.name,
            ]
        )
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return settings.OCR_CACHE_DIR / digest / f"page-{page_number:06d}.txt"


def configured_ocr_engine() -> TesseractOcrEngine | None:
    """Return configured OCR engine or None when OCR is disabled."""
    if not settings.SCRIPTURE_OCR_ENABLED:
        return None
    if settings.SCRIPTURE_OCR_ENGINE != "tesseract":
        raise OcrUnavailableError("ocr_engine_unsupported")
    return TesseractOcrEngine()
