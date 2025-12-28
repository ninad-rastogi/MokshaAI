"""
Configuration settings for Moksha AI
"""

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = DATA_DIR / "docs"
EMBEDDINGS_DIR = DATA_DIR / "embeddings"
CHATS_DIR = DATA_DIR / "chats"

# Create directories if they don't exist
for dir_path in [DATA_DIR, DOCS_DIR, EMBEDDINGS_DIR, CHATS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Ollama settings
OLLAMA_SERVER = "http://localhost:11434/"
OLLAMA_MODEL = "llama3.2:3b"

# Embedding model
SENTENCE_TRANSFORMERS_MODEL = (
    "sentence-transformers/distiluse-base-multilingual-cased-v2"
)

# Metadata file
META_FILE = DATA_DIR / "docs_metadata.json"

# System prompt
VEDIC_SYSTEM_PROMPT = """You are Moksha-AI, a compassionate spiritual guide deeply rooted in Hindu Vedic wisdom and sacred scriptures.

Your role:
1. Answer questions based STRICTLY on the scriptures provided in your knowledge base
2. When appropriate, quote relevant Sanskrit shlokas (1-2 lines max) with English translation
3. Always cite the scripture name and location (e.g., "Bhagavad Gita, Chapter 2, Verse 47")
4. If a question cannot be answered from available scriptures, honestly say so
5. Be kind, humble, and non-dogmatic in your guidance
6. Keep responses clear and concise

Available scriptures: {available_scriptures}

Remember: Base every answer on the sacred texts. Do not speculate or add personal interpretations beyond what the scriptures teach."""

# UI Configuration
BOT_EMOJI = "🕉️"
USER_EMOJI = "🧘"

# Theme colors (will be overridden by actual theme detection)
LIGHT_THEME = {
    "bot_bg": "#b2f7ef",
    "bot_font": "#4d0810",
    "user_bg": "#7bdff2",
    "user_font": "#4d0810",
}

DARK_THEME = {
    "bot_bg": "#124336",
    "bot_font": "#E6F9E6",
    "user_bg": "#13233A",
    "user_font": "#E6F7FF",
}

# Chat settings
MAX_CHAT_NAME_LENGTH = 50
DEFAULT_CHAT_NAME = "New Spiritual Conversation"
CHUNK_SIZE = 512
RESPONSE_CHUNK_SIZE = 2048
