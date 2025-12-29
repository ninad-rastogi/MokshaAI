"""
RAG engine with AI-powered intelligent query routing
No hardcoded keywords - LLM decides the routing
"""

import json
import logging
from typing import Dict, List, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.storage.chat_store import SimpleChatStore

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

        # Chat store for memory
        self.chat_store = SimpleChatStore()

        # Create classifier LLM
        self.classifier_llm = ChatOllama(
            model=ollama_model,
            base_url=ollama_server,
            temperature=0.1,  # Low temperature for consistent classification
            streaming=False,
        )

    def route_query(self, query: str) -> tuple[str, bool]:
        """
        Use LLM to intelligently route query to appropriate handler
        Returns: (route: "rag" or "general", requires_scripture: bool)
        """
        # Get list of available scriptures for context
        scriptures_list = (
            ", ".join(self.available_scriptures)
            if self.available_scriptures
            else "None"
        )

        # Classification prompt
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
            # Get classification from LLM
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
            # Remove markdown code blocks if present
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

            # Determine routing based on category
            if category == "SCRIPTURE" and self.has_documents():
                route = "rag"
                requires_scripture = True

            elif category == "SCRIPTURE" and not self.has_documents():
                # No documents available, treat as general guidance
                route = "general"
                requires_scripture = False
                logger.warning(
                    "SCRIPTURE query but no documents available, routing to GENERAL"
                )

            elif category in ["GUIDANCE", "CASUAL"]:

                route = "general"
                requires_scripture = False

            else:
                # Fallback to general
                route = "general"
                requires_scripture = False

            return route, requires_scripture

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse classification JSON: {e}, Response: {response_text}"
            )

            # Fallback to general mode
            return "general", False

        except Exception as e:
            logger.error(f"Error in query routing: {e}")
            # Fallback to general mode

            return "general", False

    def get_chat_memory(self, session_id: str) -> ChatMemoryBuffer:
        """Get or create chat memory for a session"""

        return ChatMemoryBuffer.from_defaults(
            chat_store=self.chat_store, chat_store_key=session_id
        )

    def query_with_rag(self, query: str, session_id: str) -> tuple[str, List[Dict]]:
        """Query using RAG with scripture context - returns complete response"""

        chat_memory = self.get_chat_memory(session_id)

        # Create chat engine WITHOUT streaming
        chat_engine = self.index.as_chat_engine(
            chat_mode="condense_question",
            streaming=False,  # Disable streaming to save memory
            chat_memory=chat_memory,
            similarity_top_k=3,
            verbose=True,
        )

        # Prepend system instructions to the query
        enhanced_query = f"{self.system_prompt}\n\nUser question: {query}"

        # Get complete response (non-streaming)
        response = chat_engine.chat(enhanced_query)

        # Extract response text
        response_text = str(response.response)

        # Extract source nodes for citations
        sources = []
        try:
            if hasattr(response, "source_nodes"):
                for node in response.source_nodes:
                    metadata = node.metadata
                    sources.append(
                        {
                            "scripture": metadata.get("scripture", "Unknown"),
                            "page": metadata.get("page", "N/A"),
                            "file_name": metadata.get("file_name", "Unknown"),
                            "score": (
                                round(node.score, 2) if hasattr(node, "score") else 0.0
                            ),
                            "text_preview": (
                                node.text[:200] + "..."
                                if len(node.text) > 200
                                else node.text
                            ),
                        }
                    )

        except Exception as e:
            logger.error(f"Failed to extract sources: {e}")

        return response_text, sources

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

        # Create LLM
        llm = ChatOllama(
            model=self.ollama_model,
            base_url=self.ollama_server,
            temperature=0.7,
            streaming=False,  # Disable streaming
        )

        # Get complete response using invoke
        response = llm.invoke(chat_msgs)

        # Extract text from response
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
