"""Celery tasks for safe, auditable scripture indexing."""

import hashlib
import logging
import uuid
from pathlib import Path

import fitz
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from chat.models import DocumentChunk
from chat.rag.embeddings import PgVectorStore
from chat.rag.loader import ScriptureDocumentLoader
from scriptures.models import IndexingJob, Volume

logger = logging.getLogger("scriptures.tasks")


def compute_file_hash(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with file_path.open("rb") as file_handle:
        for block in iter(lambda: file_handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


@shared_task(bind=True, autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def index_scripture(self, job_id: int) -> None:
    """Build a new scripture index before atomically removing stale chunks."""
    job = IndexingJob.objects.select_related("scripture").get(pk=job_id)
    scripture = job.scripture
    IndexingJob.objects.filter(pk=job.pk).update(
        status=IndexingJob.Status.RUNNING,
        started_at=timezone.now(),
        progress=5,
        celery_task_id=self.request.id or "",
    )
    try:
        scripture_path = Path(scripture.folder_path)
        pdf_files = sorted(scripture_path.glob("*.pdf"))
        if not pdf_files:
            raise FileNotFoundError(f"No PDFs found for {scripture.name}")

        loader = ScriptureDocumentLoader()
        chunks = []
        volumes = []
        for number, pdf_path in enumerate(pdf_files, start=1):
            stat = pdf_path.stat()
            with fitz.open(str(pdf_path)) as pdf:
                page_count = len(pdf)
            volumes.append((pdf_path, stat, page_count, compute_file_hash(pdf_path)))
            chunks.extend(loader._load_pdf(pdf_path, scripture.name))
            IndexingJob.objects.filter(pk=job.pk).update(
                progress=min(70, 5 + int(number / len(pdf_files) * 65))
            )
        if not chunks:
            raise ValueError("No extractable text was found in the PDFs.")

        # Write new version first. Keep existing retrieval available on failure.
        version = uuid.uuid4()
        added = PgVectorStore().add_chunks(chunks, index_version=version)
        IndexingJob.objects.filter(pk=job.pk).update(progress=85)

        with transaction.atomic():
            for pdf_path, stat, page_count, content_hash in volumes:
                Volume.objects.update_or_create(
                    scripture=scripture,
                    file_name=pdf_path.name,
                    defaults={
                        "file_path": str(pdf_path),
                        "file_size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "page_count": page_count,
                        "content_hash": content_hash,
                    },
                )
            DocumentChunk.objects.filter(scripture=scripture.name).exclude(
                index_version=version
            ).delete()
            scripture.total_volumes = len(volumes)
            scripture.total_pages = sum(volume[2] for volume in volumes)
            scripture.is_indexed = True
            scripture.last_indexed_at = timezone.now()
            scripture.save(
                update_fields=[
                    "total_volumes",
                    "total_pages",
                    "is_indexed",
                    "last_indexed_at",
                ]
            )
            IndexingJob.objects.filter(pk=job.pk).update(
                status=IndexingJob.Status.SUCCEEDED,
                progress=100,
                chunks_indexed=added,
                volumes_processed=len(volumes),
                finished_at=timezone.now(),
                error_message="",
            )
    except Exception as exc:
        logger.exception("Scripture indexing failed for job %s", job_id)
        IndexingJob.objects.filter(pk=job.pk).update(
            status=IndexingJob.Status.FAILED,
            error_message=str(exc)[:4000],
            finished_at=timezone.now(),
        )
        raise
