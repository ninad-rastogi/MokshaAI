"""
Document loader with scripture-aware metadata enrichment
Handles PDF loading with page-level granularity
"""

import logging
from pathlib import Path
from typing import Dict, List

import fitz  # PyMuPDF for better PDF handling
from llama_index.core import Document
from llama_index.core.readers import SimpleDirectoryReader

logger = logging.getLogger("moksha_ai.document_loader")


class ScriptureDocumentLoader:
    """Load and process scripture PDFs with metadata enrichment"""

    def __init__(self, docs_dir: Path):
        self.docs_dir = docs_dir
        self.available_scriptures = self._scan_scriptures()

    def _scan_scriptures(self) -> List[str]:
        """Scan docs directory for scripture folders"""

        scriptures = []

        if not self.docs_dir.exists():
            logger.warning(f"Docs directory not found: {self.docs_dir}")

            return scriptures

        for item in self.docs_dir.iterdir():
            if item.is_dir():

                # Check if directory has any PDFs
                if any(item.glob("*.pdf")):
                    scriptures.append(item.name)

        logger.info(f"Found scriptures: {', '.join(scriptures)}")

        return scriptures

    def load_documents_with_metadata(self) -> List[Document]:
        """Load all PDFs with page-level metadata"""

        all_documents = []

        for scripture_name in self.available_scriptures:
            scripture_path = self.docs_dir / scripture_name
            logger.info(f"Loading scripture: {scripture_name}")

            # Get all PDFs in this scripture folder
            pdf_files = list(scripture_path.glob("*.pdf"))

            for pdf_path in pdf_files:
                docs = self._load_pdf_with_pages(pdf_path, scripture_name)
                all_documents.extend(docs)
                logger.info(f"Loaded {len(docs)} pages from {pdf_path.name}")

        logger.info(f"Total documents loaded: {len(all_documents)}")

        return all_documents

    def _load_pdf_with_pages(
        self, pdf_path: Path, scripture_name: str
    ) -> List[Document]:
        """Load a PDF and split into page-level documents with metadata"""

        documents = []

        try:
            # Open PDF with PyMuPDF for better page extraction
            pdf_doc = fitz.open(str(pdf_path))

            for page_num in range(len(pdf_doc)):
                page = pdf_doc[page_num]
                text = page.get_text()

                # Skip empty pages
                if not text.strip():
                    continue

                # Create document with enriched metadata
                doc = Document(
                    text=text,
                    metadata={
                        "scripture": scripture_name,
                        "file_name": pdf_path.name,
                        "page": page_num + 1,  # 1-indexed for human readability
                        "file_path": str(pdf_path),
                        "total_pages": len(pdf_doc),
                    },
                )
                documents.append(doc)

            pdf_doc.close()

        except Exception as e:
            logger.error(f"Error loading PDF {pdf_path}: {e}")

            # Fallback to SimpleDirectoryReader if PyMuPDF fails
            try:
                reader = SimpleDirectoryReader(input_files=[str(pdf_path)])
                docs = reader.load_data()

                for doc in docs:
                    doc.metadata.update(
                        {
                            "scripture": scripture_name,
                            "file_name": pdf_path.name,
                            "file_path": str(pdf_path),
                        }
                    )

                documents.extend(docs)

            except Exception as fallback_e:
                logger.error(
                    f"Fallback loading also failed for {pdf_path}: {fallback_e}"
                )

        return documents

    def get_available_scriptures(self) -> List[str]:
        """Return list of available scripture names"""

        return self.available_scriptures

    def get_scripture_summary(self) -> Dict[str, int]:
        """Get summary of available scriptures and their file counts"""

        summary = {}

        for scripture_name in self.available_scriptures:
            scripture_path = self.docs_dir / scripture_name
            pdf_count = len(list(scripture_path.glob("*.pdf")))
            summary[scripture_name] = pdf_count

        return summary

    def get_scripture_files(self):
        """
        Returns a dictionary of scriptures and their associated files.

        Returns:
            dict: {scripture_name: [file_list]} or empty dict if no files found
        """
        scripture_files = {}

        # Assuming your docs are organized in data/docs/ directory
        import os

        docs_path = "data/docs"

        if not os.path.exists(docs_path):
            return scripture_files

        # Group files by scripture (subdirectory)
        for item in os.listdir(docs_path):
            item_path = os.path.join(docs_path, item)

            if os.path.isdir(item_path):
                files = [f for f in os.listdir(item_path) if f.endswith(".pdf")]
                scripture_files[item] = files

        return scripture_files
