"""
Embeddings and vector store management
"""

import json
import logging
import shutil
from pathlib import Path
from typing import List

import chromadb
from llama_index.core import (
    Document,
    Settings,
    StorageContext,
    VectorStoreIndex,
)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.chroma import ChromaVectorStore

logger = logging.getLogger("moksha_ai.embeddings")


class EmbeddingsManager:
    """Manage vector embeddings and index"""

    def __init__(
        self,
        embeddings_dir: Path,
        meta_file: Path,
        embed_model_name: str,
        ollama_model: str,
        ollama_server: str,
    ):
        self.embeddings_dir = embeddings_dir
        self.meta_file = meta_file
        self.embed_model_name = embed_model_name
        self.ollama_model = ollama_model
        self.ollama_server = ollama_server

        # Initialize Settings
        Settings.embed_model = HuggingFaceEmbedding(model_name=embed_model_name)
        Settings.llm = Ollama(
            model=ollama_model, base_url=ollama_server, request_timeout=480.0
        )

    def _scan_docs_metadata(self, docs_dir: Path) -> dict:
        """Scan documents and create metadata based on file stats"""

        meta = {}

        if not docs_dir.exists():
            return meta

        for item in docs_dir.rglob("*.pdf"):
            stat = item.stat()
            meta[str(item)] = {"mtime": stat.st_mtime, "size": stat.st_size}

        return meta

    def _load_stored_metadata(self) -> dict:
        """Load previously stored metadata"""

        if not self.meta_file.exists():
            return {}

        try:
            with open(self.meta_file, "r") as f:
                return json.load(f)

        except Exception as e:
            logger.warning(f"Failed to load metadata: {e}")

            return {}

    def _save_metadata(self, metadata: dict):
        """Save metadata to file"""

        try:
            with open(self.meta_file, "w") as f:
                json.dump(metadata, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def needs_rebuild(self, docs_dir: Path) -> bool:
        """Check if embeddings need to be rebuilt"""
        current_meta = self._scan_docs_metadata(docs_dir)
        stored_meta = self._load_stored_metadata()

        return current_meta != stored_meta

    def build_index(
        self, documents: List[Document], docs_dir: Path
    ) -> VectorStoreIndex:
        """Build or load vector index"""

        if self.needs_rebuild(docs_dir):
            logger.info("Documents changed. Rebuilding embeddings...")

            # Clear old embeddings
            if self.embeddings_dir.exists():
                shutil.rmtree(self.embeddings_dir)

            self.embeddings_dir.mkdir(parents=True, exist_ok=True)

            # Save new metadata
            current_meta = self._scan_docs_metadata(docs_dir)
            self._save_metadata(current_meta)

            # Create new index
            db = chromadb.PersistentClient(path=str(self.embeddings_dir))
            collection = db.get_or_create_collection("moksha_ai")
            vector_store = ChromaVectorStore(chroma_collection=collection)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)

            if documents:
                index = VectorStoreIndex.from_documents(
                    documents,
                    embed_model=Settings.embed_model,
                    storage_context=storage_context,
                )

                logger.info("Embeddings built successfully")

            else:
                index = VectorStoreIndex.from_vector_store(
                    vector_store, storage_context=storage_context
                )

                logger.warning("No documents found, created empty index")
        else:
            logger.info("Using cached embeddings")
            db = chromadb.PersistentClient(path=str(self.embeddings_dir))
            collection = db.get_or_create_collection("moksha_ai")
            vector_store = ChromaVectorStore(chroma_collection=collection)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            index = VectorStoreIndex.from_vector_store(
                vector_store, storage_context=storage_context
            )

        return index
