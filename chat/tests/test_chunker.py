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


def test_chunker_pairs_ocr_sanskrit_verse_with_hindi_translation():
    chunker = ScriptureChunker()

    chunks = chunker.chunk_page(
        (
            "यज्ञे विभूतिं तां दृष्ट्वा दुःखामर्षान्वितस्य च ।\n"
            "दुर्योधनस्यावहासो भीमेन च सभातले ।। १३६ ।।\n\n"
            "पाण्डवोंका यह वैभव देखकर दुर्योधन दुःख और ईर्ष्यासे जलने लगा ।। १३६ ।।"
        ),
        scripture_name="Mahabharata",
        file_name="Mahabharata Volume 1.pdf",
        page_num=101,
        total_pages=2256,
    )

    assert chunks[0]["chunk_type"] == "verse_with_translation"
    assert chunks[0]["language"] == "sa"
    assert "Sanskrit verse:" in chunks[0]["text"]
    assert "यज्ञे विभूतिं तां दृष्ट्वा" in chunks[0]["text"]
    assert "Translation:" in chunks[0]["text"]
    assert "पाण्डवोंका यह वैभव देखकर" in chunks[0]["text"]
