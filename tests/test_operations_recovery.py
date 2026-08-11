from datetime import timedelta

import pytest
from django.utils import timezone

from moksha.tasks import recover_stale_jobs
from scriptures.models import IndexingJob, Scripture, ScriptureIndexVersion
from users.models import User


@pytest.mark.django_db
def test_recover_stale_jobs_fails_orphan_building_index_versions(
    settings,
) -> None:
    settings.JOB_STALE_MINUTES = 30
    operator = User.objects.create_user(
        email="operator@example.test",
        password="StrongPass123!",
    )
    scripture = Scripture.objects.create(
        name="Recovery Library",
        folder_path="Recovery Library",
    )
    orphan = ScriptureIndexVersion.objects.create(
        scripture=scripture,
        embedding_model="test-embedding",
        status=ScriptureIndexVersion.Status.BUILDING,
    )
    active = ScriptureIndexVersion.objects.create(
        scripture=scripture,
        embedding_model="test-embedding",
        status=ScriptureIndexVersion.Status.BUILDING,
    )
    IndexingJob.objects.create(
        scripture=scripture,
        requested_by=operator,
        index_version=active,
        status=IndexingJob.Status.RUNNING,
        started_at=timezone.now(),
    )
    stale_created_at = timezone.now() - timedelta(hours=2)
    ScriptureIndexVersion.objects.filter(pk=orphan.pk).update(
        created_at=stale_created_at,
    )

    result = recover_stale_jobs()

    orphan.refresh_from_db()
    active.refresh_from_db()
    assert result["index_versions"] == 1
    assert orphan.status == ScriptureIndexVersion.Status.FAILED
    assert orphan.failure_code == "orphan_build_interrupted"
    assert active.status == ScriptureIndexVersion.Status.BUILDING


@pytest.mark.django_db
def test_recover_stale_jobs_keeps_long_running_index_with_fresh_heartbeat(
    settings,
) -> None:
    settings.JOB_STALE_MINUTES = 30
    operator = User.objects.create_user(
        email="indexer@example.test",
        password="StrongPass123!",
    )
    scripture = Scripture.objects.create(
        name="Long OCR Library",
        folder_path="Long OCR Library",
    )
    version = ScriptureIndexVersion.objects.create(
        scripture=scripture,
        embedding_model="test-embedding",
        status=ScriptureIndexVersion.Status.BUILDING,
    )
    stale_started_at = timezone.now() - timedelta(hours=2)
    job = IndexingJob.objects.create(
        scripture=scripture,
        requested_by=operator,
        index_version=version,
        status=IndexingJob.Status.RUNNING,
        started_at=stale_started_at,
        heartbeat_at=timezone.now(),
        progress=42,
        chunks_indexed=1258,
        error_message="ocr_fallback_running",
    )

    result = recover_stale_jobs()

    job.refresh_from_db()
    version.refresh_from_db()
    assert result["indexing_jobs"] == 0
    assert job.status == IndexingJob.Status.RUNNING
    assert job.error_message == "ocr_fallback_running"
    assert version.status == ScriptureIndexVersion.Status.BUILDING
