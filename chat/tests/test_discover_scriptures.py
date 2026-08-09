from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.management import call_command

from scriptures.models import IndexingJob, Scripture


@pytest.fixture
def scripture_folder(settings, tmp_path: Path) -> Path:
    settings.DOCS_DIR = tmp_path
    folder = tmp_path / "Open Wisdom Collection"
    folder.mkdir()
    (folder / "volume.pdf").write_bytes(b"%PDF-1.4")
    return folder


@pytest.mark.django_db
def test_discovery_reuses_pending_job(scripture_folder, django_user_model):
    operator = django_user_model.objects.create_user(
        email="operator@example.com",
        password="test-password",
        is_staff=True,
    )
    scripture = Scripture.objects.create(
        name=scripture_folder.name,
        folder_path=str(scripture_folder),
    )
    job = IndexingJob.objects.create(scripture=scripture, requested_by=operator)

    with patch(
        "chat.management.commands.discover_scriptures.index_scripture.apply"
    ) as apply:
        apply.side_effect = lambda **_kwargs: IndexingJob.objects.filter(
            pk=job.pk
        ).update(
            status=IndexingJob.Status.SUCCEEDED,
            chunks_indexed=3,
        )
        call_command("discover_scriptures")

    assert IndexingJob.objects.filter(scripture=scripture).count() == 1
    apply.assert_called_once_with(args=[job.pk], throw=True)


@pytest.mark.django_db
def test_discovery_skips_running_job(scripture_folder, django_user_model, capsys):
    operator = django_user_model.objects.create_user(
        email="operator@example.com",
        password="test-password",
        is_staff=True,
    )
    scripture = Scripture.objects.create(
        name=scripture_folder.name,
        folder_path=str(scripture_folder),
    )
    job = IndexingJob.objects.create(
        scripture=scripture,
        requested_by=operator,
        status=IndexingJob.Status.RUNNING,
    )

    with patch(
        "chat.management.commands.discover_scriptures.index_scripture.apply"
    ) as apply:
        call_command("discover_scriptures")

    assert f"indexing job {job.pk} is already running" in capsys.readouterr().out
    apply.assert_not_called()


@pytest.mark.django_db
def test_discovery_resumes_running_job_only_when_requested(
    scripture_folder, django_user_model
):
    operator = django_user_model.objects.create_user(
        email="operator@example.com",
        password="test-password",
        is_staff=True,
    )
    scripture = Scripture.objects.create(
        name=scripture_folder.name,
        folder_path=str(scripture_folder),
    )
    job = IndexingJob.objects.create(
        scripture=scripture,
        requested_by=operator,
        status=IndexingJob.Status.RUNNING,
    )

    with patch(
        "chat.management.commands.discover_scriptures.index_scripture.apply"
    ) as apply:
        apply.side_effect = lambda **_kwargs: IndexingJob.objects.filter(
            pk=job.pk
        ).update(status=IndexingJob.Status.SUCCEEDED)
        call_command("discover_scriptures", resume_running=True)

    apply.assert_called_once_with(args=[job.pk], throw=True)


@pytest.mark.django_db
def test_discovery_skips_completed_index_without_force(
    scripture_folder, django_user_model, capsys
):
    django_user_model.objects.create_user(
        email="operator@example.com",
        password="test-password",
        is_staff=True,
    )
    Scripture.objects.create(
        name=scripture_folder.name,
        folder_path=str(scripture_folder),
        is_indexed=True,
    )

    with patch(
        "chat.management.commands.discover_scriptures.index_scripture.apply"
    ) as apply:
        call_command("discover_scriptures")

    assert "already indexed" in capsys.readouterr().out
    apply.assert_not_called()
