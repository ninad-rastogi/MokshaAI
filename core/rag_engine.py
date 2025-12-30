"""
RAG engine with improved AI-powered intelligent query routing
"""

import json
import logging
from typing import Dict, List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from llama_index.core import Settings, VectorStoreIndex

logger = logging.getLogger("moksha_ai.rag_engine")


class RAGEngine:
    """RAG-based question answering with intelligent routing"""

    def __init__(
        self,
        index: VectorStoreIndex,
        ollama_model: str,
        ollama_server: str,
        system_prompt: str,
        available_scriptures: List[str],
    ):
        self.index = index
        self.ollama_model = ollama_model
        self.ollama_server = ollama_server
        self.available_scriptures = available_scriptures

        # Format system prompt
        self.system_prompt = system_prompt.format(
            available_scriptures=(
                ", ".join(available_scriptures)
                if available_scriptures
                else "None available"
            )
        )

        # Create classifier LLM
        self.classifier_llm = ChatOllama(
            model=ollama_model, base_url=ollama_server, temperature=0.1, streaming=False
        )

        # Create response LLM
        self.response_llm = ChatOllama(
            model=ollama_model, base_url=ollama_server, temperature=0.7, streaming=False
        )

    def route_query(self, query: str) -> tuple[str, bool]:
        """
        Use LLM to intelligently route query
        Returns: (route: "rag" or "general", requires_scripture: bool)
        """

        scriptures_list = (
            ", ".join(self.available_scriptures)
            if self.available_scriptures
            else "None"
        )

        classification_prompt = f"""You are a query classifier for Moksha AI, a spiritual AI assistant.

Classify the user's query into ONE of these categories:

1. **SCRIPTURE** - User explicitly asks about specific scriptures, verses, or teachings FROM texts
   Examples:
   - "What does Bhagavad Gita say about karma?"
   - "Tell me the story of Rama from Ramayana"
   - "Quote a shloka about dharma"
   - "Explain Chapter 2 of the Gita"
   
2. **GUIDANCE** - User asks for spiritual guidance, life advice, or philosophical questions
   Examples:
   - "How can I find inner peace?"
   - "What should I do when stressed?"
   - "How to practice meditation?"
   - "What is the purpose of life?"
   
3. **CASUAL** - Greetings, gratitude, meta-questions about the bot, or non-spiritual topics
   Examples:
   - "Hi", "Hello", "How are you?"
   - "Who are you?", "What can you do?"
   - "Thank you", "Thanks"
   - "How to bake a cake?"
   - "What's the weather?"

Available scriptures: {scriptures_list}

**CRITICAL RULES:**
- If query asks "who are you" or "what are you" or "introduce yourself" → CASUAL (meta-question about bot)
- If query mentions specific scripture names (Gita, Ramayana, etc.) AND asks about their content → SCRIPTURE
- If query asks for life advice, guidance, or "how to" for spiritual matters → GUIDANCE
- If query is about non-spiritual topics (cooking, coding, weather) → CASUAL
- If no scriptures available, SCRIPTURE queries become GUIDANCE

User Query: "{query}"

Respond with ONLY valid JSON:
{{
  "category": "SCRIPTURE" or "GUIDANCE" or "CASUAL",
  "reasoning": "brief explanation"
}}"""

        try:
            messages = [
                SystemMessage(
                    content="You are an expert query classifier. Respond with valid JSON only."
                ),
                HumanMessage(content=classification_prompt),
            ]

            response = self.classifier_llm.invoke(messages)
            response_text = (
                response.content if hasattr(response, "content") else str(response)
            )

            # Parse JSON
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

            # Route based on category
            if category == "SCRIPTURE" and self.has_documents():
                route = "rag"
                requires_scripture = True

            elif category == "SCRIPTURE" and not self.has_documents():
                route = "general"
                requires_scripture = False
                logger.warning("SCRIPTURE query but no documents, routing to GENERAL")

            else:
                route = "general"
                requires_scripture = False

            return route, requires_scripture

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}, Response: {response_text}")

            return "general", False

        except Exception as e:
            logger.error(f"Error in routing: {e}")

            return "general", False

    def query_with_rag(
        self, query: str, session_id: str, messages_history: List[Dict] = None
    ) -> tuple[str, List[Dict]]:
        """
        Custom RAG implementation using .invoke()
        Returns: (response_text, sources)
        """

        # Retrieve relevant documents
        retriever = self.index.as_retriever(similarity_top_k=3)
        nodes = retriever.retrieve(query)

        # Format context
        context_parts = []
        sources = []

        for i, node in enumerate(nodes):
            context_parts.append(f"[Context {i+1}]\n{node.text}\n")

            metadata = node.metadata

            sources.append(
                {
                    "scripture": metadata.get("scripture", "Unknown"),
                    "page": metadata.get("page", "N/A"),
                    "file_name": metadata.get("file_name", "Unknown"),
                    "score": round(node.score, 2) if hasattr(node, "score") else 0.0,
                    "text_preview": (
                        node.text[:200] + "..." if len(node.text) > 200 else node.text
                    ),
                }
            )

        context_str = "\n".join(context_parts)

        # Build conversation (only recent history to avoid confusion)
        chat_msgs = [SystemMessage(content=self.system_prompt)]

        if messages_history:
            for msg in messages_history:
                if msg["role"] == "user":
                    chat_msgs.append(HumanMessage(content=msg["content"]))

                elif msg["role"] == "assistant":
                    chat_msgs.append(SystemMessage(content=msg["content"]))

        # Create prompt with context
        rag_prompt = f"""Based ONLY on the following scripture context, answer the user's question.

Scripture Context:
{context_str}

User Question: {query}

Instructions:
- Answer STRICTLY from the provided context
- Quote Sanskrit shlokas if present
- Cite scripture name and page number
- If context doesn't answer the question, say so
- Do NOT refer to previous questions or conversations
- Be clear and concise"""

        chat_msgs.append(HumanMessage(content=rag_prompt))

        # Get response
        try:
            response = self.response_llm.invoke(chat_msgs)
            response_text = (
                response.content if hasattr(response, "content") else str(response)
            )

            logger.info(f"RAG response generated with {len(sources)} sources")

            return response_text, sources

        except Exception as e:
            logger.error(f"Error in RAG response: {e}")

            raise

    def query_without_rag(self, query: str, messages_history: List[Dict]) -> str:
        """Query without RAG - returns complete response"""

        # Build message history (only recent to avoid confusion)
        chat_msgs = [SystemMessage(content=self.system_prompt)]

        for msg in messages_history:
            if msg["role"] == "user":
                chat_msgs.append(HumanMessage(content=msg["content"]))

            elif msg["role"] == "assistant":
                chat_msgs.append(SystemMessage(content=msg["content"]))

        # Add current query with specific instruction
        enhanced_query = f"""{query}

IMPORTANT: Answer this NEW question directly. Do NOT refer to or mention previous questions in the conversation."""

        chat_msgs.append(HumanMessage(content=enhanced_query))

        # Get response
        response = self.response_llm.invoke(chat_msgs)
        response_text = (
            response.content if hasattr(response, "content") else str(response)
        )

        return response_text

    def has_documents(self) -> bool:
        """Check if index has documents"""

        try:
            retriever = self.index.as_retriever(similarity_top_k=1)
            results = retriever.retrieve("test")

            return len(results) > 0

        except Exception as e:
            return False

    def get_scripture_info(self) -> str:
        """Get formatted string of available scriptures"""

        if not self.available_scriptures:
            return "No scriptures loaded. Add PDFs to docs folder."

        return f"Available scriptures: {', '.join(self.available_scriptures)}"
