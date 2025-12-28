"""
RAG engine with intelligent query routing using LangGraph
"""

import logging
from typing import Dict, Generator, List, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.storage.chat_store import SimpleChatStore
from typing_extensions import TypedDict

logger = logging.getLogger("moksha_ai.rag_engine")


class QueryState(TypedDict):
    """State for query routing"""

    query: str
    route: Literal["rag", "general"]
    requires_scripture: bool


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

        # Setup routing graph
        self.routing_graph = self._create_routing_graph()

    def _create_routing_graph(self) -> StateGraph:
        """Create LangGraph for intelligent query routing"""

        def classify_query(state: QueryState) -> QueryState:
            """Classify if query needs scripture lookup or general conversation"""
            query = state["query"].lower()

            # Keywords that suggest scripture lookup
            scripture_keywords = [
                "scripture",
                "shloka",
                "verse",
                "chapter",
                "gita",
                "bhagavad",
                "mahabharata",
                "ramayana",
                "upanishad",
                "veda",
                "purana",
                "says",
                "according to",
                "in the",
                "quote",
                "what does",
                "meaning of",
                "explain",
                "reference",
                "citation",
                "page",
            ]

            # Keywords for general spiritual guidance
            general_keywords = [
                "how to",
                "should i",
                "can you help",
                "advice",
                "guidance",
                "what if",
                "is it okay",
                "feeling",
                "problem",
                "issue",
                "recommend",
                "suggest",
                "think",
                "opinion",
            ]

            # Check for scripture references
            requires_scripture = any(kw in query for kw in scripture_keywords)
            is_general = any(kw in query for kw in general_keywords)

            # Route decision
            if requires_scripture:
                state["route"] = "rag"
                state["requires_scripture"] = True
            elif is_general and not requires_scripture:
                state["route"] = "general"
                state["requires_scripture"] = False
            else:
                # Default to RAG if ambiguous and we have documents
                state["route"] = "rag" if self.has_documents() else "general"
                state["requires_scripture"] = self.has_documents()

            logger.info(
                f"Query classified: route={state['route']}, requires_scripture={state['requires_scripture']}"
            )
            return state

        # Create graph
        workflow = StateGraph(QueryState)
        workflow.add_node("classify", classify_query)
        workflow.set_entry_point("classify")
        workflow.add_edge("classify", END)

        return workflow.compile()

    def route_query(self, query: str) -> tuple[str, bool]:
        """Route query to appropriate handler"""
        initial_state: QueryState = {
            "query": query,
            "route": "general",
            "requires_scripture": False,
        }

        result = self.routing_graph.invoke(initial_state)
        return result["route"], result["requires_scripture"]

    def get_chat_memory(self, session_id: str) -> ChatMemoryBuffer:
        """Get or create chat memory for a session"""
        return ChatMemoryBuffer.from_defaults(
            chat_store=self.chat_store, chat_store_key=session_id
        )

    def query_with_rag(
        self, query: str, session_id: str, streaming: bool = True
    ) -> tuple[Generator, List[Dict]]:
        """Query using RAG with scripture context"""

        chat_memory = self.get_chat_memory(session_id)

        # Create chat engine WITHOUT system_prompt (not supported by CondenseQuestionChatEngine)
        chat_engine = self.index.as_chat_engine(
            chat_mode="condense_question",
            streaming=streaming,
            chat_memory=chat_memory,
            similarity_top_k=3,
            verbose=True,
        )

        # Prepend system instructions to the query
        enhanced_query = f"{self.system_prompt}\n\nUser question: {query}"

        # Stream response
        response_stream = chat_engine.stream_chat(enhanced_query)

        # Extract source nodes for citations
        sources = []
        try:
            if hasattr(response_stream, "source_nodes"):
                for node in response_stream.source_nodes:
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

        response_gen = getattr(response_stream, "response_gen", response_stream)

        return response_gen, sources

    def query_without_rag(
        self, query: str, messages_history: List[Dict], streaming: bool = True
    ) -> Generator:
        """Query without RAG (general spiritual guidance)"""

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
            streaming=streaming,
        )

        # Stream response
        response_gen = llm.stream(chat_msgs)

        return response_gen

    def has_documents(self) -> bool:
        """Check if index has any documents"""
        try:
            retriever = self.index.as_retriever(similarity_top_k=1)
            results = retriever.retrieve("test")
            return len(results) > 0
        except:
            return False

    def get_scripture_info(self) -> str:
        """Get formatted string of available scriptures"""
        if not self.available_scriptures:
            return "No scriptures currently loaded. Please add PDF files to the docs folder."

        return f"Available scriptures: {', '.join(self.available_scriptures)}"
