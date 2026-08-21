from unittest.mock import patch

import pytest
from django.test import override_settings

from moksha.tasks import auto_discover_scripture_indexes
from scriptures.models import IndexingJob, Scripture, ScriptureIndexVersion
from users.models import User


@pytest.mark.django_db
def test_auto_discover_scripture_indexes_noops_without_staff(tmp_path) -> None:
    docs_dir = tmp_path / "docs"
    collection = docs_dir / "Katha Upanishad"
    collection.mkdir(parents=True)
    (collection / "volume.pdf").write_bytes(b"%PDF-1.7\n")

    with override_settings(DOCS_DIR=docs_dir):
        result = auto_discover_scripture_indexes()

    assert result == {"discovered": 0, "queued": 0, "skipped": 0, "no_staff": 1}
    assert Scripture.objects.count() == 0


@pytest.mark.django_db
def test_auto_discover_scripture_indexes_queues_unindexed_collection(
    tmp_path,
    django_capture_on_commit_callbacks,
) -> None:
    User.objects.create_user(
        email="staff@example.test",
        password="StrongPass123!",
        is_staff=True,
    )
    docs_dir = tmp_path / "docs"
    collection = docs_dir / "Katha Upanishad"
    collection.mkdir(parents=True)
    (collection / "volume.pdf").write_bytes(b"%PDF-1.7\n")

    with (
        override_settings(DOCS_DIR=docs_dir),
        patch("scriptures.tasks.index_scripture.delay") as delay,
        django_capture_on_commit_callbacks(execute=True),
    ):
        result = auto_discover_scripture_indexes()

    scripture = Scripture.objects.get(name="Katha Upanishad")
    job = IndexingJob.objects.get(scripture=scripture)
    assert result == {"discovered": 1, "queued": 1, "skipped": 0}
    assert scripture.folder_path == str(collection)
    delay.assert_called_once_with(job.pk)


@pytest.mark.django_db
def test_auto_discover_scripture_indexes_skips_active_job(tmp_path) -> None:
    operator = User.objects.create_user(
        email="staff@example.test",
        password="StrongPass123!",
        is_staff=True,
    )
    docs_dir = tmp_path / "docs"
    collection = docs_dir / "Katha Upanishad"
    collection.mkdir(parents=True)
    (collection / "volume.pdf").write_bytes(b"%PDF-1.7\n")
    scripture = Scripture.objects.create(
        name="Katha Upanishad",
        folder_path=str(collection),
    )
    IndexingJob.objects.create(
        scripture=scripture,
        requested_by=operator,
        status=IndexingJob.Status.RUNNING,
    )

    with (
        override_settings(DOCS_DIR=docs_dir),
        patch("scriptures.tasks.index_scripture.delay") as delay,
    ):
        result = auto_discover_scripture_indexes()

    assert result == {"discovered": 1, "queued": 0, "skipped": 1}
    delay.assert_not_called()


@pytest.mark.django_db
def test_auto_discover_scripture_indexes_resumes_best_failed_checkpoint(
    tmp_path,
    django_capture_on_commit_callbacks,
) -> None:
    operator = User.objects.create_user(
        email="staff@example.test",
        password="StrongPass123!",
        is_staff=True,
    )
    docs_dir = tmp_path / "docs"
    collection = docs_dir / "Katha Upanishad"
    collection.mkdir(parents=True)
    (collection / "volume.pdf").write_bytes(b"%PDF-1.7\n")
    scripture = Scripture.objects.create(
        name="Katha Upanishad",
        folder_path=str(collection),
    )
    empty_version = ScriptureIndexVersion.objects.create(
        scripture=scripture,
        embedding_model="test-embedding",
        status=ScriptureIndexVersion.Status.FAILED,
        failure_code="index_ocr_unavailable",
        source_manifest=[{"file_name": "volume.pdf", "sha256": "a", "pages": 1}],
    )
    empty_job = IndexingJob.objects.create(
        scripture=scripture,
        requested_by=operator,
        index_version=empty_version,
        status=IndexingJob.Status.FAILED,
        progress=70,
        chunks_indexed=0,
        error_message="index_ocr_unavailable",
    )
    checkpoint_version = ScriptureIndexVersion.objects.create(
        scripture=scripture,
        embedding_model="test-embedding",
        status=ScriptureIndexVersion.Status.FAILED,
        failure_code="index_interrupted_for_progress_fix",
        source_manifest=[{"file_name": "volume.pdf", "sha256": "b", "pages": 1}],
    )
    checkpoint_job = IndexingJob.objects.create(
        scripture=scripture,
        requested_by=operator,
        index_version=checkpoint_version,
        status=IndexingJob.Status.FAILED,
        progress=70,
        chunks_indexed=9608,
        error_message="index_interrupted_for_progress_fix",
    )

    with (
        override_settings(DOCS_DIR=docs_dir),
        patch("scriptures.tasks.index_scripture.delay") as delay,
        django_capture_on_commit_callbacks(execute=True),
    ):
        result = auto_discover_scripture_indexes()

    empty_job.refresh_from_db()
    checkpoint_job.refresh_from_db()
    checkpoint_version.refresh_from_db()
    assert result == {"discovered": 1, "queued": 1, "skipped": 0}
    assert empty_job.status == IndexingJob.Status.FAILED
    assert checkpoint_job.status == IndexingJob.Status.PENDING
    assert checkpoint_version.status == ScriptureIndexVersion.Status.BUILDING
    delay.assert_called_once_with(checkpoint_job.pk)
