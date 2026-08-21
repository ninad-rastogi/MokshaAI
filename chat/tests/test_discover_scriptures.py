from pathlib import Path
from unittest.mock import call, patch

import pytest
from celery.exceptions import Retry
from django.core.management import CommandError, call_command

from scriptures.models import IndexingJob, Scripture, ScriptureIndexVersion
from scriptures.tasks import INDEX_FAILURE_BUILD, INDEX_FAILURE_OCR_UNAVAILABLE


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
        call_command(
            "discover_scriptures",
            resume_running=True,
            confirm_worker_stopped=True,
        )

    apply.assert_called_once_with(args=[job.pk], throw=True)


@pytest.mark.django_db
def test_discovery_resume_running_requires_stopped_confirmation(
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
    IndexingJob.objects.create(
        scripture=scripture,
        requested_by=operator,
        status=IndexingJob.Status.RUNNING,
    )

    with (
        patch(
            "chat.management.commands.discover_scriptures.index_scripture.apply"
        ) as apply,
        pytest.raises(CommandError, match="confirm-worker-stopped"),
    ):
        call_command("discover_scriptures", resume_running=True)

    apply.assert_not_called()


@pytest.mark.django_db
def test_discovery_replays_eager_task_retry(scripture_folder, django_user_model):
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

    attempts = 0

    def retry_then_complete(**_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise Retry("transient dependency")
        IndexingJob.objects.filter(pk=job.pk).update(
            status=IndexingJob.Status.SUCCEEDED
        )

    with patch(
        "chat.management.commands.discover_scriptures.index_scripture.apply"
    ) as apply:
        apply.side_effect = retry_then_complete
        call_command(
            "discover_scriptures",
            resume_running=True,
            confirm_worker_stopped=True,
        )

    assert apply.call_args_list == [
        call(args=[job.pk], throw=True),
        call(args=[job.pk], throw=True, retries=1),
    ]


@pytest.mark.django_db
def test_discovery_resumes_failed_build_candidate(scripture_folder, django_user_model):
    operator = django_user_model.objects.create_user(
        email="operator@example.com",
        password="test-password",
        is_staff=True,
    )
    scripture = Scripture.objects.create(
        name=scripture_folder.name,
        folder_path=str(scripture_folder),
    )
    version = ScriptureIndexVersion.objects.create(
        scripture=scripture,
        embedding_model="test-embedding",
        status=ScriptureIndexVersion.Status.FAILED,
        failure_code=INDEX_FAILURE_BUILD,
        source_manifest=[{"file_name": "volume.pdf", "sha256": "a", "pages": 1}],
    )
    job = IndexingJob.objects.create(
        scripture=scripture,
        requested_by=operator,
        index_version=version,
        status=IndexingJob.Status.FAILED,
        progress=71,
        chunks_indexed=320,
        error_message=INDEX_FAILURE_BUILD,
    )
    recovered_state = {}

    def complete_recovered_job(**_kwargs):
        job.refresh_from_db()
        version.refresh_from_db()
        recovered_state.update(
            job_status=job.status,
            job_chunks=job.chunks_indexed,
            version_status=version.status,
        )
        IndexingJob.objects.filter(pk=job.pk).update(
            status=IndexingJob.Status.SUCCEEDED
        )

    with patch(
        "chat.management.commands.discover_scriptures.index_scripture.apply"
    ) as apply:
        apply.side_effect = complete_recovered_job
        call_command("discover_scriptures", resume_failed=True)

    assert recovered_state == {
        "job_status": IndexingJob.Status.PENDING,
        "job_chunks": 320,
        "version_status": ScriptureIndexVersion.Status.BUILDING,
    }
    apply.assert_called_once_with(args=[job.pk], throw=True)


@pytest.mark.django_db
def test_discovery_resumes_failed_ocr_unavailable_candidate(
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
    version = ScriptureIndexVersion.objects.create(
        scripture=scripture,
        embedding_model="test-embedding",
        status=ScriptureIndexVersion.Status.FAILED,
        failure_code=INDEX_FAILURE_OCR_UNAVAILABLE,
        source_manifest=[{"file_name": "volume.pdf", "sha256": "a", "pages": 1}],
    )
    job = IndexingJob.objects.create(
        scripture=scripture,
        requested_by=operator,
        index_version=version,
        status=IndexingJob.Status.FAILED,
        progress=20,
        chunks_indexed=3203,
        error_message=INDEX_FAILURE_OCR_UNAVAILABLE,
    )
    recovered_state = {}

    def complete_recovered_job(**_kwargs):
        job.refresh_from_db()
        version.refresh_from_db()
        recovered_state.update(
            job_status=job.status,
            job_error=job.error_message,
            version_status=version.status,
            version_failure=version.failure_code,
        )
        IndexingJob.objects.filter(pk=job.pk).update(
            status=IndexingJob.Status.SUCCEEDED
        )

    with patch(
        "chat.management.commands.discover_scriptures.index_scripture.apply"
    ) as apply:
        apply.side_effect = complete_recovered_job
        call_command("discover_scriptures", resume_failed=True)

    assert recovered_state == {
        "job_status": IndexingJob.Status.PENDING,
        "job_error": "",
        "version_status": ScriptureIndexVersion.Status.BUILDING,
        "version_failure": "",
    }
    apply.assert_called_once_with(args=[job.pk], throw=True)


@pytest.mark.django_db
def test_discovery_resumes_best_failed_ocr_checkpoint(
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
    empty_version = ScriptureIndexVersion.objects.create(
        scripture=scripture,
        embedding_model="test-embedding",
        status=ScriptureIndexVersion.Status.FAILED,
        failure_code=INDEX_FAILURE_OCR_UNAVAILABLE,
        source_manifest=[{"file_name": "volume.pdf", "sha256": "a", "pages": 1}],
    )
    empty_job = IndexingJob.objects.create(
        scripture=scripture,
        requested_by=operator,
        index_version=empty_version,
        status=IndexingJob.Status.FAILED,
        progress=70,
        chunks_indexed=0,
        error_message=INDEX_FAILURE_OCR_UNAVAILABLE,
    )
    checkpoint_version = ScriptureIndexVersion.objects.create(
        scripture=scripture,
        embedding_model="test-embedding",
        status=ScriptureIndexVersion.Status.FAILED,
        failure_code=INDEX_FAILURE_OCR_UNAVAILABLE,
        source_manifest=[{"file_name": "volume.pdf", "sha256": "b", "pages": 1}],
    )
    checkpoint_job = IndexingJob.objects.create(
        scripture=scripture,
        requested_by=operator,
        index_version=checkpoint_version,
        status=IndexingJob.Status.FAILED,
        progress=62,
        chunks_indexed=9608,
        error_message=INDEX_FAILURE_OCR_UNAVAILABLE,
    )

    def complete_recovered_job(**_kwargs):
        IndexingJob.objects.filter(pk=checkpoint_job.pk).update(
            status=IndexingJob.Status.SUCCEEDED
        )

    with patch(
        "chat.management.commands.discover_scriptures.index_scripture.apply"
    ) as apply:
        apply.side_effect = complete_recovered_job
        call_command("discover_scriptures", resume_failed=True)

    empty_job.refresh_from_db()
    checkpoint_job.refresh_from_db()
    assert empty_job.status == IndexingJob.Status.FAILED
    assert checkpoint_job.status == IndexingJob.Status.SUCCEEDED
    apply.assert_called_once_with(args=[checkpoint_job.pk], throw=True)


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
