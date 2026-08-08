from chat.rag.chunker import ScriptureChunker


def test_chunker_pairs_adjacent_shloka_and_translation():
    chunker = ScriptureChunker()

    chunks = chunker.chunk_page(
        "सत्यं वद।\n\nSpeak truth.\n\nA later note.",
        scripture_name="Collection",
        file_name="volume.pdf",
        page_num=7,
        total_pages=10,
    )

    first = chunks[0]
    assert first["chunk_type"] == "verse_with_translation"
    assert first["page"] == 7
    assert first["scripture"] == "Collection"
    assert "Sanskrit verse:\nसत्यं वद।" in first["text"]
    assert "Translation:\nSpeak truth." in first["text"]
    assert chunks[1]["text"] == "A later note."
