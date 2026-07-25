# chat/rag/ — RAG (Retrieval-Augmented Generation) Engine

This subpackage contains the **core intelligence** of Moksha AI. It handles query routing,
document loading, embedding storage, and AI-powered responses. This is adapted from the old
`core/` package but redesigned to work with Django and PgVector.

## Purpose

The RAG engine:
1. **Routes queries**: Uses an LLM to classify user questions into SCRIPTURE, GUIDANCE, or CASUAL
2. **Retrieves context**: Searches PgVector for relevant scripture chunks
3. **Generates responses**: Uses Ollama (`moksha-qwen3:4b-instruct-q3km`) to generate answers grounded in scriptures
4. **Manages embeddings**: Stores and searches vector embeddings in PostgreSQL via PgVector

## Files

### `engine.py` — RAGEngine Class

The main RAG engine with two key methods:

**`route_query(query)` → (route, requires_scripture):**
- Uses an LLM (temperature=0.1) to classify the query
- Returns `("rag", True)` for scripture questions, `("general", False)` for others
- Classification prompt includes examples and critical rules
- Falls back to "general" on any error

**`query_with_rag(query, messages_history)` → (response_text, sources):**
- Retrieves top-3 relevant chunks from PgVector
- Builds a context string from retrieved chunks
- Constructs a conversation with system prompt + recent history + RAG prompt
- Uses Ollama (temperature=0.7) to generate the response
- Returns response + source citations (scripture, page, score, preview)

**`query_without_rag(query, messages_history)` → response_text:**
- For GUIDANCE and CASUAL queries
- Uses the Vedic system prompt but no scripture retrieval
- Handles general spiritual conversation

### `embeddings.py` — PgVectorStore Class

Replaces the old ChromaDB-based `core/embeddings.py`. Uses PostgreSQL's PgVector extension.

**Key methods:**

- **`initialize_table()`**: Creates the `document_chunks` table with:
  - Columns: id, scripture, file_name, page, chunk_text, chunk_type, language, embedding
  - HNSW index for fast cosine similarity search (m=16, ef_construction=64)
  - B-tree index on scripture name for filtering

- **`add_chunks(chunks, batch_size=32)`**: Embeds and stores document chunks:
  - Uses `BAAI/bge-m3` model (better for mixed Sanskrit/Hindi/English)
  - Batch processing for efficiency
  - Returns count of added chunks

- **`search(query, top_k=3, scripture_filter=None)`**: Searches for similar chunks:
  - Uses cosine distance (`<=>` operator in PgVector)
  - Optional scripture name filter
  - Returns list of dicts with text, metadata, and similarity score

- **`clear_scripture(scripture_name)`**: Removes all chunks for a scripture (for re-indexing)
- **`count()`**: Total chunks in the store
- **`get_scriptures()`**: List of unique scripture names

**Why PgVector over ChromaDB?**
- Single database for all data (users, chats, vectors) — no separate service
- ACID compliance — vectors and relational data stay in sync
- HNSW indexing — fast similarity search
- No extra Docker container or configuration needed
- For the scale of this project (thousands of chunks), PgVector is more than fast enough

### `loader.py` — ScriptureDocumentLoader Class

Loads and processes scripture PDFs. Adapted from `core/document_loader.py`.

**Key methods:**

- **`_scan_scriptures()`**: Scans `data/docs/` for subdirectories containing PDFs
- **`load_all()`**: Loads all scriptures and returns chunked documents
- **`load_scripture(name)`**: Loads a single scripture by name
- **`_load_pdf(path, name)`**: Opens a PDF with PyMuPDF, extracts text page-by-page,
  and uses `ScriptureChunker` to split into semantic chunks

**Auto-discovery**: Just add a folder with PDFs under `data/docs/` and run
`python manage.py discover_scriptures`.

### `chunker.py` — ScriptureChunker Class

**NEW in v2.0** — Splits page-level text into semantic units. This is critical because
Sanskrit shlokas and their Hindi translations carry different meanings.

**Key methods:**

- **`chunk_page(text, scripture_name, file_name, page_num, total_pages)`**:
  Splits a page into typed sections, then into chunks with metadata.

- **`_split_sections(text)`**: Groups consecutive lines by type (shloka/translation/narration)

- **`_classify_line(line)`**: Classifies a line using Devanagari ratio detection:
  - >60% Devanagari characters → "shloka"
  - 10-60% Devanagari → "translation"
  - <10% Devanagari → "narration"

- **`_detect_language(text)`**: Returns "sa" (Sanskrit), "hi" (Hindi), or "en" (English)

- **`_split_long_text(text)`**: Splits text exceeding `max_chunk_size` (1000 chars) at
  sentence boundaries

**Why semantic chunking matters:**
- Sanskrit shlokas are poetic verses with specific meter and meaning
- Hindi translations explain the shloka in prose
- Narration provides context and storytelling
- Indexing them separately means a user asking "What does the Gita say about karma?"
  will match against the Hindi translation (which carries the semantic meaning)
  while still getting the Sanskrit shloka as a citation
