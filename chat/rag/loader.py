"""
Scripture document loader with auto-discovery.

Adapted from core/document_loader.py to work with Django settings.
Loads PDFs from data/docs/<ScriptureName>/ directories.
"""

import logging
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from django.conf import settings

from chat.rag.chunker import ScriptureChunker

logger = logging.getLogger("chat.rag.loader")


class ScriptureDocumentLoader:
    """Load and process scripture PDFs with metadata enrichment."""

    def __init__(self, docs_dir: Path | None = None):
        self.docs_dir = docs_dir or settings.DOCS_DIR
        self.chunker = ScriptureChunker()

    @property
    def available_scriptures(self) -> list[str]:
        """Return current PDF collections without requiring a process restart."""
        return self._scan_scriptures()

    @staticmethod
    def _pdf_files(collection_path: Path) -> list[Path]:
        """Return regular PDFs from every volume folder in one collection."""
        return sorted(
            (
                path
                for path in collection_path.rglob("*.pdf")
                if path.is_file() and not path.is_symlink()
            ),
            key=lambda path: str(path.relative_to(collection_path)).casefold(),
        )

    def _scan_scriptures(self) -> list[str]:
        """Scan docs directory for scripture folders."""
        scriptures: list[str] = []

        if not self.docs_dir.exists():
            logger.warning(f"Docs directory not found: {self.docs_dir}")
            return scriptures

        for item in sorted(
            self.docs_dir.iterdir(), key=lambda path: path.name.casefold()
        ):
            if item.is_dir() and not item.is_symlink() and self._pdf_files(item):
                scriptures.append(item.name)

        logger.info("Discovered %d scripture collections", len(scriptures))
        return scriptures

    def load_all(self) -> list[dict[str, Any]]:
        """
        Load all scripture PDFs and return chunked documents.

        Returns:
            List of chunk dicts with keys:
                scripture, file_name, page, text,
                chunk_type, language
        """
        all_chunks: list[dict[str, Any]] = []

        for scripture_name in self.available_scriptures:
            scripture_path = self.docs_dir / scripture_name
            logger.info(f"Loading scripture: {scripture_name}")

            pdf_files = self._pdf_files(scripture_path)

            for pdf_path in pdf_files:
                chunks = self._load_pdf(pdf_path, scripture_name)
                all_chunks.extend(chunks)
                logger.info(f"Loaded {len(chunks)} chunks from {pdf_path.name}")

        logger.info(f"Total chunks loaded: {len(all_chunks)}")
        return all_chunks

    def load_scripture(self, scripture_name: str) -> list[dict[str, Any]]:
        """Load a single scripture by name."""
        scripture_path = self.docs_dir / scripture_name

        if not scripture_path.exists():
            logger.error(f"Scripture not found: {scripture_name}")
            return []

        all_chunks: list[dict[str, Any]] = []
        for pdf_path in self._pdf_files(scripture_path):
            chunks = self._load_pdf(pdf_path, scripture_name)
            all_chunks.extend(chunks)

        return all_chunks

    def _load_pdf(self, pdf_path: Path, scripture_name: str) -> list[dict[str, Any]]:
        """Load a PDF and split into semantic chunks."""
        chunks: list[dict[str, Any]] = []

        try:
            pdf_doc = fitz.open(str(pdf_path))

            for page_num in range(len(pdf_doc)):
                page = pdf_doc[page_num]
                text = page.get_text()

                if not text.strip():
                    continue

                # Use the semantic chunker to split page content
                page_chunks = self.chunker.chunk_page(
                    text=text,
                    scripture_name=scripture_name,
                    file_name=pdf_path.name,
                    page_num=page_num + 1,
                    total_pages=len(pdf_doc),
                )
                chunks.extend(page_chunks)

            pdf_doc.close()

        except Exception:
            logger.exception("Could not load PDF %s", pdf_path.name)

        return chunks

    def get_available_scriptures(self) -> list[str]:
        """Return list of available scripture names."""
        return self.available_scriptures

    def get_scripture_summary(self) -> dict[str, int]:
        """Get summary of available scriptures and their file counts."""
        summary: dict[str, int] = {}
        for scripture_name in self.available_scriptures:
            scripture_path = self.docs_dir / scripture_name
            pdf_count = len(self._pdf_files(scripture_path))
            summary[scripture_name] = pdf_count
        return summary
