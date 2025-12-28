__version__ = "1.0.0"

from .chat_manager import ChatManager
from .config import (
    CHATS_DIR,
    DOCS_DIR,
    EMBEDDINGS_DIR,
    OLLAMA_MODEL,
    OLLAMA_SERVER,
    VEDIC_SYSTEM_PROMPT,
)
from .document_loader import ScriptureDocumentLoader
from .embeddings import EmbeddingsManager
from .rag_engine import RAGEngine

__all__ = [
    "DOCS_DIR",
    "EMBEDDINGS_DIR",
    "CHATS_DIR",
    "OLLAMA_MODEL",
    "OLLAMA_SERVER",
    "VEDIC_SYSTEM_PROMPT",
    "ScriptureDocumentLoader",
    "EmbeddingsManager",
    "ChatManager",
    "RAGEngine",
]
