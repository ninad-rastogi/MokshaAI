"""API tests for scripture indexing visibility."""

import pytest
from rest_framework.test import APIClient

from scriptures.models import IndexingJob, Scripture, ScriptureIndexVersion
from users.models import User


@pytest.mark.django_db
def test_scripture_list_exposes_bounded_active_indexing_progress() -> None:
    user = User.objects.create_user(
        email="scripture-progress@example.test",
        password="StrongPass123!",
    )
    scripture = Scripture.objects.create(
        name="Living wisdom",
        folder_path="Living wisdom",
    )
    index_version = ScriptureIndexVersion.objects.create(
        scripture=scripture,
        embedding_model="bge-m3",
        volume_count=6,
        page_count=128,
    )
    IndexingJob.objects.create(
        scripture=scripture,
        index_version=index_version,
        requested_by=user,
        status=IndexingJob.Status.RUNNING,
        progress=71,
        chunks_indexed=6720,
        volumes_processed=6,
        error_message="private_internal_detail",
    )
    client = APIClient()
    client.force_authenticate(user)

    response = client.get("/api/v1/scriptures/")

    assert response.status_code == 200
    progress = response.data["results"][0]["current_indexing_job"]
    assert progress == {
        "status": "RUNNING",
        "phase": "embedding",
        "progress": 71,
        "chunks_indexed": 6720,
        "ocr_pages_processed": 0,
        "ocr_checkpoint_pages": 0,
        "is_replaying_checkpoint": False,
        "volumes_processed": 6,
        "source_volumes": 6,
        "source_pages": 128,
    }
    assert "error_message" not in progress


@pytest.mark.django_db
def test_scripture_list_derives_ocr_progress_from_scanned_pages() -> None:
    user = User.objects.create_user(
        email="scripture-ocr-progress@example.test",
        password="StrongPass123!",
    )
    scripture = Scripture.objects.create(
        name="Living wisdom OCR",
        folder_path="Living wisdom OCR",
    )
    index_version = ScriptureIndexVersion.objects.create(
        scripture=scripture,
        embedding_model="bge-m3",
        volume_count=6,
        page_count=15432,
    )
    IndexingJob.objects.create(
        scripture=scripture,
        index_version=index_version,
        requested_by=user,
        status=IndexingJob.Status.RUNNING,
        progress=70,
        chunks_indexed=8351,
        ocr_pages_processed=1200,
        ocr_checkpoint_pages=8351,
        volumes_processed=3,
        error_message="ocr_fallback_running",
    )
    client = APIClient()
    client.force_authenticate(user)

    response = client.get("/api/v1/scriptures/")

    assert response.status_code == 200
    progress = response.data["results"][0]["current_indexing_job"]
    assert progress["phase"] == "ocr"
    assert progress["progress"] == 70
    assert progress["chunks_indexed"] == 8351
    assert progress["ocr_pages_processed"] == 1200
    assert progress["ocr_checkpoint_pages"] == 8351
    assert progress["is_replaying_checkpoint"] is True
    assert progress["source_pages"] == 15432


@pytest.mark.django_db
def test_scripture_list_does_not_mislabel_embedding_as_ocr() -> None:
    user = User.objects.create_user(
        email="scripture-embedding-progress@example.test",
        password="StrongPass123!",
    )
    scripture = Scripture.objects.create(
        name="Living wisdom embeddings",
        folder_path="Living wisdom embeddings",
    )
    index_version = ScriptureIndexVersion.objects.create(
        scripture=scripture,
        embedding_model="bge-m3",
        volume_count=6,
        page_count=15432,
    )
    IndexingJob.objects.create(
        scripture=scripture,
        index_version=index_version,
        requested_by=user,
        status=IndexingJob.Status.RUNNING,
        progress=74,
        chunks_indexed=4096,
        volumes_processed=6,
        error_message="",
    )
    client = APIClient()
    client.force_authenticate(user)

    response = client.get("/api/v1/scriptures/")

    assert response.status_code == 200
    progress = response.data["results"][0]["current_indexing_job"]
    assert progress["phase"] == "embedding"
    assert progress["progress"] == 74


@pytest.mark.django_db
def test_scripture_list_exposes_only_bounded_latest_failure() -> None:
    user = User.objects.create_user(
        email="scripture-failure@example.test",
        password="StrongPass123!",
    )
    scripture = Scripture.objects.create(
        name="Unreadable source",
        folder_path="Unreadable source",
    )
    IndexingJob.objects.create(
        scripture=scripture,
        requested_by=user,
        status=IndexingJob.Status.FAILED,
        error_message="index_source_text_corrupt",
    )
    client = APIClient()
    client.force_authenticate(user)

    response = client.get("/api/v1/scriptures/")

    assert response.status_code == 200
    result = response.data["results"][0]
    assert result["current_indexing_job"] is None
    assert result["latest_indexing_failure"] == {
        "failure_code": "index_source_text_corrupt",
        "finished_at": None,
    }
    assert "error_message" not in result["latest_indexing_failure"]
