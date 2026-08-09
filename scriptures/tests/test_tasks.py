"""Tests for durable scripture indexing progress."""

from uuid import UUID

import pytest

from chat.models import DocumentChunk
from chat.rag.embeddings import EmbeddingServiceError
from scriptures.models import IndexingJob, Scripture
from scriptures.tasks import (
    MAX_SUSPICIOUS_SOURCE_RATIO,
    candidate_can_retry,
    candidate_checkpoint,
    index_progress_floor,
    record_embedding_progress,
    source_text_quality,
)
from users.models import User


@pytest.mark.parametrize(
    "error",
    [OSError("filesystem unavailable"), EmbeddingServiceError("sidecar unavailable")],
)
def test_candidate_retries_transient_dependencies(error: Exception) -> None:
    assert candidate_can_retry(error, retries=0, max_retries=3)
    assert not candidate_can_retry(error, retries=3, max_retries=3)


@pytest.mark.django_db
def test_record_embedding_progress_persists_chunks_and_bounded_percent() -> None:
    operator = User.objects.create_user(
        email="index-progress@example.test",
        password="StrongPass123!",
    )
    scripture = Scripture.objects.create(
        name="Progress collection",
        folder_path="Progress collection",
    )
    job = IndexingJob.objects.create(
        scripture=scripture,
        requested_by=operator,
        status=IndexingJob.Status.RUNNING,
        progress=70,
    )

    record_embedding_progress(job.pk, completed=96, total=128)
    job.refresh_from_db()

    assert job.chunks_indexed == 96
    assert job.progress == 80

    record_embedding_progress(job.pk, completed=128, total=128)
    job.refresh_from_db()

    assert job.progress == 84


@pytest.mark.django_db
def test_candidate_checkpoint_uses_committed_chunk_count() -> None:
    version_id = UUID("2cf122c5-e54c-4ac2-a7ea-d18a51aa20c7")
    DocumentChunk.objects.bulk_create(
        [
            DocumentChunk(
                scripture="Progress collection",
                file_name="volume.pdf",
                page=index + 1,
                chunk_text=f"passage {index}",
                index_version=version_id,
            )
            for index in range(2)
        ]
    )

    assert candidate_checkpoint(version_id, total_chunks=3) == 2

    with pytest.raises(RuntimeError, match="index_checkpoint_invalid"):
        candidate_checkpoint(version_id, total_chunks=1)


def test_candidate_retry_is_limited_to_remaining_os_error_attempts() -> None:
    assert candidate_can_retry(OSError("temporary"), retries=1, max_retries=3)
    assert not candidate_can_retry(OSError("exhausted"), retries=3, max_retries=3)
    assert not candidate_can_retry(RuntimeError("invalid"), retries=0, max_retries=3)


def test_resumed_index_progress_never_moves_backward() -> None:
    assert index_progress_floor(current=82, resuming=True) == 82
    assert index_progress_floor(current=59, resuming=True) == 70
    assert index_progress_floor(current=100, resuming=False) == 5


def test_source_text_quality_accepts_clean_devanagari_verse() -> None:
    report = source_text_quality(
        [
            {
                "chunk_type": "verse_with_translation",
                "text": "Sanskrit verse:\nकर्मण्येवाधिकारस्ते मा फलेषु कदाचन।",
            },
            {"chunk_type": "narration", "text": "A plain English note."},
        ]
    )

    assert report == {
        "devanagari_chunks": 1,
        "suspicious_source_chunks": 0,
        "suspicious_source_ratio": 0.0,
        "max_suspicious_source_ratio": MAX_SUSPICIOUS_SOURCE_RATIO,
        "source_text_qualified": True,
    }


def test_source_text_quality_rejects_pdf_font_mojibake() -> None:
    report = source_text_quality(
        [
            {"chunk_type": "shloka", "text": "Æवमेव माता च ȵपता Æवमेव"},
            {"chunk_type": "shloka", "text": "ĜीमÊमहɍषɢ वेदȉासĒणीत"},
            {"chunk_type": "shloka", "text": "सत्यं वद।"},
        ]
    )

    assert report["suspicious_source_chunks"] == 2
    assert report["suspicious_source_ratio"] == 0.6667
    assert report["source_text_qualified"] is False


def test_source_text_quality_does_not_require_verses_for_prose_collection() -> None:
    report = source_text_quality(
        [{"chunk_type": "narration", "text": "A prose spiritual collection."}]
    )

    assert report["devanagari_chunks"] == 0
    assert report["source_text_qualified"] is True


def test_source_text_quality_checks_devanagari_prose_chunks() -> None:
    report = source_text_quality(
        [{"chunk_type": "translation", "text": "यह ĜीमÊ दूषित पाठ है।"}]
    )

    assert report["suspicious_source_chunks"] == 1
    assert report["source_text_qualified"] is False
