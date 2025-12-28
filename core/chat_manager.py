"""
Chat session management with smart naming
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

logger = logging.getLogger("moksha_ai.chat_manager")


class ChatManager:
    """Manage chat sessions, history, and smart naming"""

    def __init__(
        self,
        chats_dir: Path,
        ollama_model: str,
        ollama_server: str,
        max_name_length: int = 50,
    ):
        self.chats_dir = chats_dir
        self.ollama_model = ollama_model
        self.ollama_server = ollama_server
        self.max_name_length = max_name_length

        # Ensure chats directory exists
        self.chats_dir.mkdir(parents=True, exist_ok=True)

    def create_new_chat(self) -> str:
        """Create a new chat session and return its ID"""

        chat_id = str(uuid.uuid4())

        chat_data = {
            "id": chat_id,
            "name": "New Spiritual Conversation",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "messages": [],
        }

        self._save_chat(chat_id, chat_data)
        logger.info(f"Created new chat: {chat_id}")
        return chat_id

    def _save_chat(self, chat_id: str, chat_data: dict):
        """Save chat data to JSON file"""

        file_path = self.chats_dir / f"{chat_id}.json"

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(chat_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to save chat {chat_id}: {e}")

    def load_chat(self, chat_id: str) -> Optional[Dict]:
        """Load chat data from JSON file"""
        file_path = self.chats_dir / f"{chat_id}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)

        except Exception as e:
            logger.error(f"Failed to load chat {chat_id}: {e}")

            return None

    def get_all_chats(self) -> List[Dict]:
        """Get all chat sessions sorted by last updated"""
        chats = []

        for file_path in self.chats_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    chat_data = json.load(f)
                    chats.append(
                        {
                            "id": chat_data.get("id", file_path.stem),
                            "name": chat_data.get("name", "Untitled Chat"),
                            "updated_at": chat_data.get("updated_at", ""),
                            "message_count": len(chat_data.get("messages", [])),
                        }
                    )

            except Exception as e:
                logger.error(f"Failed to read chat file {file_path}: {e}")

        # Sort by updated_at (most recent first)
        chats.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

        return chats

    def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat session"""
        file_path = self.chats_dir / f"{chat_id}.json"

        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted chat: {chat_id}")

                return True

            return False

        except Exception as e:
            logger.error(f"Failed to delete chat {chat_id}: {e}")

            return False

    def rename_chat(self, chat_id: str, new_name: str) -> bool:
        """Rename a chat session"""
        chat_data = self.load_chat(chat_id)

        if not chat_data:

            return False

        chat_data["name"] = new_name[: self.max_name_length]
        chat_data["updated_at"] = datetime.now().isoformat()
        self._save_chat(chat_id, chat_data)
        logger.info(f"Renamed chat {chat_id} to: {new_name}")

        return True

    def add_message(self, chat_id: str, role: str, content: str, mode: str = None):
        """Add a message to chat history"""
        chat_data = self.load_chat(chat_id)

        if not chat_data:
            chat_data = {
                "id": chat_id,
                "name": "New Spiritual Conversation",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "messages": [],
            }

        chat_data["messages"].append(
            {
                "role": role,
                "content": content,
                "mode": mode,
                "timestamp": datetime.now().isoformat(),
            }
        )

        chat_data["updated_at"] = datetime.now().isoformat()

        # Auto-name chat after first user message
        if len(chat_data["messages"]) == 1 and role == "user":
            self._auto_name_chat(chat_id, chat_data, content)

        self._save_chat(chat_id, chat_data)

    def _auto_name_chat(self, chat_id: str, chat_data: dict, first_message: str):
        """Generate a smart name for the chat based on first message"""

        try:
            llm = ChatOllama(
                model=self.ollama_model, base_url=self.ollama_server, temperature=0.3
            )

            naming_prompt = f"""Based on this spiritual question, create a short, meaningful title (max 6 words):

Question: {first_message[:200]}

Generate ONLY the title, nothing else. Make it spiritual and relevant."""

            messages = [
                SystemMessage(
                    content="You are a helpful assistant that creates concise, meaningful titles."
                ),
                HumanMessage(content=naming_prompt),
            ]

            response = llm.invoke(messages)

            # Extract title
            title = response.content.strip().strip('"').strip("'")

            # Truncate if too long
            if len(title) > self.max_name_length:
                title = title[: self.max_name_length - 3] + "..."

            chat_data["name"] = title
            logger.info(f"Auto-named chat {chat_id}: {title}")

        except Exception as e:
            logger.error(f"Failed to auto-name chat: {e}")
            # Keep default name if auto-naming fails

    def get_messages(self, chat_id: str) -> List[Dict]:
        """Get all messages from a chat"""
        chat_data = self.load_chat(chat_id)

        if not chat_data:
            return []

        return chat_data.get("messages", [])

    def clear_all_chats(self) -> int:
        """Clear all chat history (use with caution)"""
        count = 0

        for file_path in self.chats_dir.glob("*.json"):
            try:
                file_path.unlink()
                count += 1

            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")

        logger.info(f"Cleared {count} chats")

        return count
