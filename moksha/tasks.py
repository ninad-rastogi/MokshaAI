"""Scheduled operational recovery, disk checks, and bounded cleanup."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("moksha.operations")


def disk_report(paths: list[Path]) -> list[dict[str, object]]:
    report: list[dict[str, object]] = []
    for path in paths:
        try:
            path.mkdir(parents=True, exist_ok=True)
            usage = shutil.disk_usage(path)
        except OSError:
            report.append(
                {
                    "path": str(path),
                    "total": 0,
                    "used": 0,
                    "free": 0,
                    "healthy": False,
                }
            )
            continue
        report.append(
            {
                "path": str(path),
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "healthy": usage.free >= settings.DISK_MIN_FREE_BYTES,
            }
        )
    return report


@shared_task(queue="operations")
def monitor_disk_space() -> list[dict[str, object]]:
    report = disk_report(
        [
            Path(settings.DATA_DIR),
            Path(settings.OLLAMA_IMPORTS_DIR),
        ]
    )
    if not all(bool(item["healthy"]) for item in report):
        logger.error("Disk free space below configured minimum")
    return report


@shared_task(queue="operations")
def recover_stale_jobs() -> dict[str, int]:
    from chat.models import GenerationAttempt, GenerationRun
    from llm.models import ModelInstallationJob
    from scriptures.models import IndexingJob, ScriptureIndexVersion

    cutoff = timezone.now() - timedelta(minutes=settings.JOB_STALE_MINUTES)
    generation_ids = list(
        GenerationRun.objects.filter(
            state__in=[
                GenerationRun.State.QUEUED,
                GenerationRun.State.RUNNING,
            ],
            updated_at__lt=cutoff,
        ).values_list("pk", flat=True)
    )
    generations = GenerationRun.objects.filter(pk__in=generation_ids).update(
        state=GenerationRun.State.FAILED,
        error_code="worker_restarted",
        finished_at=timezone.now(),
    )
    GenerationAttempt.objects.filter(
        run_id__in=generation_ids,
        outcome=GenerationAttempt.Outcome.STARTED,
    ).update(
        outcome=GenerationAttempt.Outcome.FAILED,
        error_code="worker_restarted",
        finished_at=timezone.now(),
    )
    stale_index_jobs = IndexingJob.objects.filter(
        status=IndexingJob.Status.RUNNING,
        started_at__lt=cutoff,
    )
    stale_version_ids = list(
        stale_index_jobs.exclude(index_version=None).values_list(
            "index_version_id",
            flat=True,
        )
    )
    indexing = stale_index_jobs.update(
        status=IndexingJob.Status.FAILED,
        error_message="worker_restarted",
        finished_at=timezone.now(),
    )
    ScriptureIndexVersion.objects.filter(
        pk__in=stale_version_ids,
        status__in=[
            ScriptureIndexVersion.Status.BUILDING,
            ScriptureIndexVersion.Status.QUALIFIED,
        ],
    ).update(
        status=ScriptureIndexVersion.Status.FAILED,
        failure_code="worker_restarted",
    )
    installations = ModelInstallationJob.objects.filter(
        status=ModelInstallationJob.Status.RUNNING,
        started_at__lt=cutoff,
    ).update(
        status=ModelInstallationJob.Status.FAILED,
        active_lock=False,
        error_code="worker_restarted",
        finished_at=timezone.now(),
    )
    return {
        "generation_runs": generations,
        "indexing_jobs": indexing,
        "model_installations": installations,
    }


@shared_task(queue="operations")
def cleanup_stale_model_parts() -> int:
    from llm.models import ModelCatalogRelease

    cutoff = timezone.now() - timedelta(hours=settings.MODEL_PART_MAX_AGE_HOURS)
    allowed_names: set[str] = set()
    for release in ModelCatalogRelease.objects.all():
        entries = release.payload.get("entries", [])
        for entry in entries if isinstance(entries, list) else []:
            if isinstance(entry, dict) and isinstance(entry.get("file"), str):
                allowed_names.add(f"{entry['file']}.part")
    imports_dir = Path(settings.OLLAMA_IMPORTS_DIR).resolve()
    removed = 0
    if not imports_dir.is_dir():
        return removed
    for path in imports_dir.iterdir():
        if (
            path.is_file()
            and path.name in allowed_names
            and datetime.fromtimestamp(
                path.stat().st_mtime,
                tz=timezone.get_current_timezone(),
            )
            < cutoff
        ):
            path.unlink()
            removed += 1
    return removed
