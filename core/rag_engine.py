"""
RAG engine with AI-powered intelligent query routing
Custom RAG implementation using .invoke() to avoid memory issues
"""

import json
import logging
from typing import Dict, List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from llama_index.core import Settings, VectorStoreIndex

logger = logging.getLogger("moksha_ai.rag_engine")


class RAGEngine:
    """RAG-based question answering with AI-powered intelligent routing"""

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

        # Format system prompt with available scriptures
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
        Use LLM to intelligently route query to appropriate handler
        Returns: (route: "rag" or "general", requires_scripture: bool)
        """

        scriptures_list = (
            ", ".join(self.available_scriptures)
            if self.available_scriptures
            else "None"
        )

        classification_prompt = f"""You are a query classifier for a spiritual AI assistant called Moksha AI.

Your job is to classify user queries into one of these categories:

1. **SCRIPTURE** - User is asking about specific scriptures, teachings, verses, or quotes
   Examples:
   - "What does Bhagavad Gita say about karma?"
   - "Tell me about the story of Rama"
   - "Quote a shloka about dharma"
   - "Explain Chapter 2 of the Gita"
   
2. **GUIDANCE** - User is asking for spiritual guidance, life advice, or philosophical discussion within the scope of spirituality
   Examples:
   - "How can I find inner peace?"
   - "What should I do when I feel stressed?"
   - "How to practice meditation?"
   - "What is the meaning of life?"
   
3. **CASUAL** - User is just chatting casually, saying hello, or asking about non-spiritual topics
   Examples:
   - "Hi", "Hello", "How are you?"
   - "Thank you", "Thanks"
   - "How to bake a cake?"
   - "What's the weather?"
   - "Tell me a joke"

Available scriptures in the database: {scriptures_list}

**IMPORTANT RULES:**
- If query asks about specific scriptures, verses, quotes, or teachings → SCRIPTURE
- If query asks for spiritual guidance, life advice, or philosophical questions → GUIDANCE
- If query is casual chat, gratitude, or about non-spiritual topics (cooking, coding, weather, etc.) → CASUAL
- If scriptures are available and query mentions them, prefer SCRIPTURE over GUIDANCE
- If no scriptures available, SCRIPTURE queries should be treated as GUIDANCE

User Query: "{query}"

Respond with ONLY a JSON object:
{{
  "category": "SCRIPTURE" or "GUIDANCE" or "CASUAL",
  "reasoning": "brief explanation of why you chose this category"
}}"""

        try:
            messages = [
                SystemMessage(
                    content="You are an expert query classifier. Always respond with valid JSON only."
                ),
                HumanMessage(content=classification_prompt),
            ]

            response = self.classifier_llm.invoke(messages)

            response_text = (
                response.content if hasattr(response, "content") else str(response)
            )

            # Parse JSON response
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
            reasoning = classification.get("reasoning", "No reasoning provided")

            logger.info(f"Query classified as: {category} - Reasoning: {reasoning}")

            if category == "SCRIPTURE" and self.has_documents():
                route = "rag"
                requires_scripture = True

            elif category == "SCRIPTURE" and not self.has_documents():
                route = "general"
                requires_scripture = False
                logger.warning(
                    "SCRIPTURE query but no documents available, routing to GENERAL"
                )

            elif category in ["GUIDANCE", "CASUAL"]:
                route = "general"
                requires_scripture = False

            else:
                route = "general"
                requires_scripture = False

            return route, requires_scripture

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse classification JSON: {e}, Response: {response_text}"
            )

            return "general", False

        except Exception as e:
            logger.error(f"Error in query routing: {e}")

            return "general", False

    def query_with_rag(
        self, query: str, session_id: str, messages_history: List[Dict] = None
    ) -> tuple[str, List[Dict]]:
        """
        Custom RAG implementation using .invoke() to avoid memory issues
        Returns: (response_text, sources)
        """

        # Step 1: Retrieve relevant documents
        retriever = self.index.as_retriever(similarity_top_k=3)
        nodes = retriever.retrieve(query)

        # Step 2: Format context from retrieved nodes
        context_parts = []
        sources = []

        for i, node in enumerate(nodes):
            context_parts.append(f"[Context {i+1}]\n{node.text}\n")

            # Extract metadata for citations
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

        # Step 3: Build conversation history
        chat_msgs = [SystemMessage(content=self.system_prompt)]

        # Add previous messages if available
        if messages_history:
            for msg in messages_history:
                if msg["role"] == "user":
                    chat_msgs.append(HumanMessage(content=msg["content"]))

                elif msg["role"] == "assistant":
                    chat_msgs.append(SystemMessage(content=msg["content"]))

        # Step 4: Create prompt with context
        rag_prompt = f"""Based on the following context from sacred scriptures, please answer the user's question.

Context from Scriptures:
{context_str}

User Question: {query}

Instructions:
- Answer based STRICTLY on the provided context
- Quote relevant Sanskrit shlokas if present in the context
- Cite the scripture name and page number
- If the context doesn't contain the answer, say so honestly
- Be clear, concise, and respectful"""

        chat_msgs.append(HumanMessage(content=rag_prompt))

        # Step 5: Get response using .invoke() (no streaming)
        try:
            response = self.response_llm.invoke(chat_msgs)
            response_text = (
                response.content if hasattr(response, "content") else str(response)
            )

            logger.info(
                f"RAG response generated successfully with {len(sources)} sources"
            )
            return response_text, sources

        except Exception as e:
            logger.error(f"Error generating RAG response: {e}")
            raise

    def query_without_rag(self, query: str, messages_history: List[Dict]) -> str:
        """Query without RAG - returns complete response"""

        # Build message history
        chat_msgs = [SystemMessage(content=self.system_prompt)]

        for msg in messages_history:
            if msg["role"] == "user":
                chat_msgs.append(HumanMessage(content=msg["content"]))

            elif msg["role"] == "assistant":
                chat_msgs.append(SystemMessage(content=msg["content"]))

        # Add current query
        chat_msgs.append(HumanMessage(content=query))

        # Get complete response using invoke
        response = self.response_llm.invoke(chat_msgs)
        response_text = (
            response.content if hasattr(response, "content") else str(response)
        )

        return response_text

    def has_documents(self) -> bool:
        """Check if index has any documents"""
        try:
            retriever = self.index.as_retriever(similarity_top_k=1)
            results = retriever.retrieve("test")
            return len(results) > 0

        except Exception as e:
            return False

    def get_scripture_info(self) -> str:
        """Get formatted string of available scriptures"""

        if not self.available_scriptures:
            return "No scriptures currently loaded. Please add PDF files to the docs folder."

        return f"Available scriptures: {', '.join(self.available_scriptures)}"
