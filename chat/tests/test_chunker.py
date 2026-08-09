from chat.rag.chunker import ScriptureChunker


def test_chunker_pairs_adjacent_shloka_and_translation():
    chunker = ScriptureChunker()

    chunks = chunker.chunk_page(
        "सत्यं वद॥ १ ॥\n\nSpeak truth.\n\nA later note.",
        scripture_name="Collection",
        file_name="volume.pdf",
        page_num=7,
        total_pages=10,
    )

    first = chunks[0]
    assert first["chunk_type"] == "verse_with_translation"
    assert first["page"] == 7
    assert first["scripture"] == "Collection"
    assert "Sanskrit verse:\nसत्यं वद॥ १ ॥" in first["text"]
    assert "Translation:\nSpeak truth." in first["text"]
    assert chunks[1]["text"] == "A later note."


def test_chunker_does_not_label_hindi_prose_as_sanskrit():
    chunker = ScriptureChunker()

    chunks = chunker.chunk_page(
        "मन को शांत रखने के लिए नियमित अभ्यास आवश्यक है।",
        scripture_name="Collection",
        file_name="volume.pdf",
        page_num=8,
        total_pages=10,
    )

    assert chunks[0]["chunk_type"] == "translation"
    assert chunks[0]["language"] == "hi"
