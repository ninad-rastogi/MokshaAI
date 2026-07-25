"""
RAG engine with intelligent query routing for Moksha AI.

Adapted from core/rag_engine.py to work with Django settings and PgVector.
"""

import json
import logging
from typing import Any

from django.conf import settings
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from chat.rag.safety import safety_response

logger = logging.getLogger("chat.rag.engine")


def _message_text(content: str | list[str | dict[str, Any]]) -> str:
    """Normalize LangChain's multimodal message content to plain text."""
    if isinstance(content, str):
        return content
    return "".join(item if isinstance(item, str) else str(item) for item in content)


class RAGEngine:
    """RAG-based question answering with intelligent query routing."""

    def __init__(
        self,
        vector_store: Any,
        ollama_model: str | None = None,
        ollama_server: str | None = None,
        system_prompt: str | None = None,
        available_scriptures: list[str] | None = None,
    ) -> None:
        self.vector_store = vector_store
        self.ollama_model = ollama_model or settings.OLLAMA_MODEL
        self.ollama_server = ollama_server or settings.OLLAMA_BASE_URL
        self.available_scriptures = available_scriptures or []

        self.system_prompt = (system_prompt or settings.VEDIC_SYSTEM_PROMPT).format(
            available_scriptures=(
                ", ".join(self.available_scriptures)
                if self.available_scriptures
                else "None available"
            )
        )

        self.classifier_llm = ChatOllama(
            model=self.ollama_model,
            base_url=self.ollama_server,
            temperature=0.1,
            client_kwargs={"timeout": settings.OLLAMA_TIMEOUT_SECONDS},
        )

        self.response_llm = ChatOllama(
            model=self.ollama_model,
            base_url=self.ollama_server,
            temperature=0.7,
            client_kwargs={"timeout": settings.OLLAMA_TIMEOUT_SECONDS},
        )

    def route_query(self, query: str) -> tuple[str, bool]:
        """
        Use LLM to intelligently route the query.

        Returns:
            tuple: (route: "rag" or "general", requires_scripture: bool)
        """
        if safety_response(query):
            return "safety", False

        scriptures_list = (
            ", ".join(self.available_scriptures)
            if self.available_scriptures
            else "None"
        )

        classification_prompt = (
            "You are a query classifier for Moksha AI, a spiritual AI "
            "assistant.\n\n"
            "Classify the user's query into ONE of these categories:\n\n"
            "1. **SCRIPTURE** - User explicitly asks about specific "
            "scriptures, verses, or teachings FROM texts\n"
            "   Examples:\n"
            '   - "What does Bhagavad Gita say about karma?"\n'
            '   - "Tell me the story of Rama from Ramayana"\n'
            '   - "Quote a shloka about dharma"\n\n'
            "2. **GUIDANCE** - User asks for spiritual guidance, life "
            "advice, or philosophical questions\n"
            "   Examples:\n"
            '   - "How can I find inner peace?"\n'
            '   - "What should I do when stressed?"\n\n'
            "3. **CASUAL** - Greetings, gratitude, meta-questions about "
            "the bot, or non-spiritual topics\n"
            "   Examples:\n"
            '   - "Hi", "Hello", "How are you?"\n'
            '   - "Thank you", "Thanks"\n'
            '   - "How to bake a cake?"\n\n'
            f"Available scriptures: {scriptures_list}\n\n"
            "**CRITICAL RULES:**\n"
            '- If query asks "who are you" or "what are you" → CASUAL\n'
            "- If query mentions specific scripture names AND asks about "
            "their content → SCRIPTURE\n"
            "- If query asks for life advice or guidance → GUIDANCE\n"
            "- If no scriptures available, SCRIPTURE queries become "
            "GUIDANCE\n\n"
            f'User Query: "{query}"\n\n'
            "Respond with ONLY valid JSON:\n"
            "{\n"
            '  "category": "SCRIPTURE" or "GUIDANCE" or "CASUAL",\n'
            '  "reasoning": "brief explanation"\n'
            "}"
        )

        try:
            messages = [
                SystemMessage(
                    content="You are an expert query classifier. "
                    "Respond with valid JSON only."
                ),
                HumanMessage(content=classification_prompt),
            ]

            response = self.classifier_llm.invoke(messages)
            response_text = _message_text(response.content)

            # Strip markdown code fences
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            classification = json.loads(response_text)
            category = classification.get("category", "GUIDANCE")
            reasoning = classification.get("reasoning", "No reasoning")

            logger.info(f"Query classified as: {category} - Reasoning: {reasoning}")

            if category == "SCRIPTURE" and self.vector_store:
                route = "rag"
                requires_scripture = True
            elif category == "SCRIPTURE" and not self.vector_store:
                route = "general"
                requires_scripture = False
                logger.warning(
                    "SCRIPTURE query but no vector store, routing to GENERAL"
                )
            else:
                route = "general"
                requires_scripture = False

            return route, requires_scripture

        except Exception as e:
            logger.error(f"Error in routing: {e}")
            return "general", False

    def query_with_rag(
        self,
        query: str,
        messages_history: list[dict[str, Any]] | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Process query using RAG.

        Returns:
            tuple: (response_text, sources)
        """
        # Retrieve relevant documents from vector store
        chunks = self.vector_store.search(
            query, top_k=3, allowed_scriptures=self.available_scriptures
        )
        chunks = [
            chunk for chunk in chunks if chunk["score"] >= settings.RAG_MIN_SIMILARITY
        ]
        if not chunks:
            return (
                "I could not find a sufficiently relevant passage in the indexed "
                "scriptures to answer that reliably. Please try a more specific "
                "question or ask for general spiritual guidance.",
                [],
            )

        context_parts = []
        sources = []

        for i, chunk in enumerate(chunks):
            context_parts.append(f"[Context {i + 1}]\n{chunk['text']}\n")
            sources.append(
                {
                    "scripture": chunk.get("scripture", "Unknown"),
                    "page": chunk.get("page", "N/A"),
                    "file_name": chunk.get("file_name", "Unknown"),
                    "score": chunk.get("score", 0.0),
                    "excerpt": (
                        chunk["text"][:200] + "..."
                        if len(chunk["text"]) > 200
                        else chunk["text"]
                    ),
                }
            )

        context_str = "\n".join(context_parts)

        # Build conversation
        chat_msgs: list[BaseMessage] = [SystemMessage(content=self.system_prompt)]

        if messages_history:
            for msg in messages_history[-6:]:
                if msg["role"] == "user":
                    chat_msgs.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    chat_msgs.append(AIMessage(content=msg["content"]))

        rag_prompt = (
            f"Based ONLY on the following scripture context, answer the "
            f"user's question.\n\n"
            f"Scripture Context:\n{context_str}\n\n"
            f"User Question: {query}\n\n"
            f"Instructions:\n"
            f"- Answer STRICTLY from the provided context\n"
            f"- Quote Sanskrit shlokas if present\n"
            f"- Cite every factual scripture claim inline as [Scripture, file, p. N]\n"
            f"- If context doesn't answer the question, say so\n"
            f"- Be clear and concise"
        )

        chat_msgs.append(HumanMessage(content=rag_prompt))

        response = self.response_llm.invoke(chat_msgs)
        response_text = _message_text(response.content)

        logger.info(f"RAG response generated with {len(sources)} sources")
        return response_text, sources

    def query_without_rag(
        self, query: str, messages_history: list[dict[str, Any]] | None = None
    ) -> str:
        """Query without RAG (general conversation)."""
        safe_response = safety_response(query)
        if safe_response:
            return safe_response
        chat_msgs: list[BaseMessage] = [SystemMessage(content=self.system_prompt)]

        if messages_history:
            for msg in messages_history[-6:]:
                if msg["role"] == "user":
                    chat_msgs.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    chat_msgs.append(AIMessage(content=msg["content"]))

        enhanced_query = (
            f"{query}\n\nIMPORTANT: Answer this NEW question directly. "
            f"Do NOT refer to or mention previous questions."
        )

        chat_msgs.append(HumanMessage(content=enhanced_query))

        response = self.response_llm.invoke(chat_msgs)
        response_text = _message_text(response.content)

        return response_text
