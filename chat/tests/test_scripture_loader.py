"""Corpus-neutral discovery tests for scripture documents."""

from pathlib import Path

from chat.rag.loader import ScriptureDocumentLoader


def touch_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n")


def test_discovers_all_pdf_collections_recursively_and_ignores_other_files(tmp_path):
    touch_pdf(tmp_path / "Wisdom Collection" / "volume-one" / "first.pdf")
    touch_pdf(tmp_path / "Meditation Collection" / "practice.pdf")
    (tmp_path / "Notes").mkdir()
    (tmp_path / "Notes" / "readme.txt").write_text("not a source", encoding="utf-8")

    loader = ScriptureDocumentLoader(tmp_path)

    assert loader.get_available_scriptures() == [
        "Meditation Collection",
        "Wisdom Collection",
    ]
    assert loader.get_scripture_summary() == {
        "Meditation Collection": 1,
        "Wisdom Collection": 1,
    }


def test_collection_discovery_reflects_files_added_after_loader_creation(tmp_path):
    loader = ScriptureDocumentLoader(tmp_path)
    assert loader.get_available_scriptures() == []

    touch_pdf(tmp_path / "New Collection" / "new-volume" / "teaching.pdf")

    assert loader.get_available_scriptures() == ["New Collection"]


def test_nested_volume_source_label_is_collection_relative(tmp_path):
    collection = tmp_path / "Wisdom Collection"
    pdf_path = collection / "volume-one" / "teaching.pdf"
    touch_pdf(pdf_path)

    assert (
        ScriptureDocumentLoader._display_file_name(pdf_path, collection)
        == "volume-one/teaching.pdf"
    )
