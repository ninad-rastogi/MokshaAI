# 🕉️ Moksha AI - Vedic Spiritual Guide

A sophisticated AI chatbot that serves as your spiritual companion, deeply rooted in Hindu Vedic wisdom and sacred scriptures. Moksha AI provides meaningful spiritual conversations, quotes authentic shlokas, and answers questions based strictly on sacred texts.

## ✨ Features

- **📚 Scripture-Based RAG**: Answers grounded in authentic Vedic texts
- **🔍 Page-Level Citations**: Precise references with scripture name and page numbers
- **💬 Smart Chat Management**: ChatGPT-like sidebar with intelligent chat naming
- **🌍 Multilingual Support**: Handles Sanskrit, Hindi, and English
- **📖 Scripture Awareness**: Automatically detects and indexes available texts
- **🎯 Context-Aware Responses**: Maintains conversation flow with chat memory
- **✏️ Chat Organization**: Rename, delete, and organize your spiritual conversations

## 🏗️ Project Structure

```
MokshaAI/
├── moksha_ai.py              # Entry point
├── requirements.txt          # Dependencies
├── README.md                 # This file
│
├── core/                     # Core business logic
│   ├── __init__.py
│   ├── config.py            # Configuration settings
│   ├── document_loader.py   # PDF loading with metadata
│   ├── embeddings.py        # Vector store management
│   ├── rag_engine.py        # RAG implementation
│   └── chat_manager.py      # Chat session management
│
├── ui/                       # User interface
│   ├── __init__.py
│   ├── main_app.py          # Main Streamlit app
│   ├── sidebar.py           # Sidebar with chat history
│   ├── chat_display.py      # Chat rendering
│   └── styles.py            # CSS and styling
│
├── data/                     # Data storage
│   ├── docs/                # Scripture PDFs (organized by folder)
│   │   ├── Mahabharata/
│   │   ├── Ramayana/
│   │   ├── Bhagavad_Gita/
│   │   └── ...
│   ├── embeddings/          # Vector store (auto-generated)
│   └── chats/               # Chat history JSON files (auto-generated)
│
└── images/                   # Logo and assets
    ├── MokshaAI_light_cropped.png
    └── MokshaAI_dark_cropped.png
```

## 🚀 Installation

### Prerequisites

1. **Python 3.10+**
2. **Ollama** installed and running locally
   ```bash
   # Install Ollama from https://ollama.ai
   # Pull the required model
   ollama pull llama3.2:3b
   ```

### Setup Steps

1. **Clone the repository**

   ```bash
   git clone <your-repo-url>
   cd MokshaAI
   ```

2. **Create virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Add scripture PDFs**

   - Create folders in `data/docs/` for each scripture (e.g., `Mahabharata`, `Ramayana`)
   - Add PDF files to respective folders
   - Example structure:
     ```
     data/docs/
     ├── Bhagavad_Gita/
     │   └── bhagavad_gita_complete.pdf
     ├── Mahabharata/
     │   ├── mahabharata_part1.pdf
     │   └── mahabharata_part2.pdf
     └── Ramayana/
         └── ramayana_complete.pdf
     ```

5. **Run the application**
   ```bash
   streamlit run moksha_ai.py
   ```

## 🎯 Usage

### Starting a New Conversation

1. Click "➕ New Conversation" in the sidebar
2. Type your spiritual question in the chat input
3. Receive answers with scripture references

### Managing Chats

- **Switch Chats**: Click on any chat in the sidebar
- **Rename**: Click the ✏️ icon next to a chat
- **Delete**: Click the 🗑️ icon to remove a chat
- **Auto-Naming**: Chats are automatically named based on the first question

### Example Questions

- "What is the meaning of dharma according to the Bhagavad Gita?"
- "Explain the concept of karma"
- "What does the Ramayana teach about devotion?"
- "How can I practice meditation according to the Vedas?"

## ⚙️ Configuration

Edit `core/config.py` to customize:

```python
# Ollama settings
OLLAMA_SERVER = "http://localhost:11434/"
OLLAMA_MODEL = "llama3.2:3b"  # Change to your preferred model

# Embedding model
SENTENCE_TRANSFORMERS_MODEL = "sentence-transformers/distiluse-base-multilingual-cased-v2"

# Chat settings
MAX_CHAT_NAME_LENGTH = 50
CHUNK_SIZE = 512
RESPONSE_CHUNK_SIZE = 2048
```

## 🔧 Technical Details

### RAG Implementation

- **Document Loading**: PyMuPDF extracts text page-by-page
- **Metadata Enrichment**: Each page tagged with scripture name, file name, and page number
- **Embeddings**: Multilingual sentence transformers for better semantic search
- **Vector Store**: ChromaDB for efficient similarity search
- **Context**: Top-3 relevant chunks retrieved for each query

### Chat Management

- **Storage**: JSON files per chat in `data/chats/`
- **Smart Naming**: LLM generates meaningful titles from first message
- **History**: Full conversation history maintained per chat
- **Memory**: RAG engine uses chat memory for context

### UI Components

- **Sidebar**: Native Streamlit sidebar with chat list
- **Streaming**: Token-by-token response streaming
- **Citations**: Expandable source references with page numbers
- **Themes**: Auto-adapts to light/dark mode

## 🐛 Troubleshooting

### No documents loaded

- Ensure PDFs are in `data/docs/<ScriptureName>/` folders
- Check PDF files are not corrupted
- Verify folder structure is correct

### Ollama connection error

- Verify Ollama is running: `ollama serve`
- Check the model is pulled: `ollama list`
- Confirm `OLLAMA_SERVER` URL in config

### Slow response times

- First-time embedding generation takes time
- Reduce `similarity_top_k` in `rag_engine.py`
- Use a smaller embedding model

### Chat history not loading

- Check `data/chats/` directory exists
- Verify JSON files are valid
- Check file permissions

## 📝 Development

### Adding New Features

1. **Core logic**: Add to respective file in `core/`
2. **UI components**: Extend classes in `ui/`
3. **Configuration**: Update `core/config.py`

### Code Style

- Follow PEP 8
- Use type hints where appropriate
- Add docstrings to functions/classes
- Log important operations

### Testing

```bash
# Run with debug logging
python moksha_ai.py --log-level DEBUG

# Test document loading
python -c "from core.document_loader import ScriptureDocumentLoader; loader = ScriptureDocumentLoader('data/docs'); print(loader.get_scripture_summary())"
```

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is open source. Please respect the sacred nature of the scriptures and use this tool with reverence.

## 🙏 Acknowledgments

- Built with Streamlit, LlamaIndex, and LangChain
- Powered by Ollama for local LLM inference
- Inspired by the timeless wisdom of Vedic texts

## 📧 Support

For issues or questions:

- Open an issue on GitHub
- Check existing documentation
- Review troubleshooting guide above

---

**May this tool serve your spiritual journey. Om Shanti. 🕉️**
