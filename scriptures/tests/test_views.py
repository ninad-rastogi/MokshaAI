"""API tests for scripture indexing visibility."""

import pytest
from rest_framework.test import APIClient

from scriptures.models import IndexingJob, Scripture
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
    IndexingJob.objects.create(
        scripture=scripture,
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
        "progress": 71,
        "chunks_indexed": 6720,
        "volumes_processed": 6,
    }
    assert "error_message" not in progress


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
