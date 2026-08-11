from unittest.mock import patch

import pytest
from django.test import override_settings

from moksha.tasks import auto_discover_scripture_indexes
from scriptures.models import IndexingJob, Scripture
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
