"""Celery tasks for safe, auditable scripture indexing."""

import hashlib
import logging
from pathlib import Path

import fitz
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from chat.models import DocumentChunk
from chat.rag.embeddings import PgVectorStore
from chat.rag.loader import ScriptureDocumentLoader
from scriptures.models import (
    IndexingJob,
    ScriptureIndexVersion,
    Volume,
)

logger = logging.getLogger("scriptures.tasks")

INDEX_FAILURE_BUILD = "index_build_failed"
INDEX_FAILURE_QUALIFICATION = "index_qualification_failed"


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
    version = ScriptureIndexVersion.objects.create(
        scripture=scripture,
        embedding_model=settings.EMBEDDING_MODEL,
    )
    IndexingJob.objects.filter(pk=job.pk).update(
        status=IndexingJob.Status.RUNNING,
        started_at=timezone.now(),
        progress=5,
        celery_task_id=self.request.id or "",
        index_version=version,
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

        source_manifest = [
            {
                "file_name": pdf_path.name,
                "sha256": content_hash,
                "size": stat.st_size,
                "pages": page_count,
            }
            for pdf_path, stat, page_count, content_hash in volumes
        ]
        version.source_manifest = source_manifest
        version.volume_count = len(volumes)
        version.page_count = sum(volume[2] for volume in volumes)
        version.save(update_fields=["source_manifest", "volume_count", "page_count"])

        # Write candidate first. Existing active retrieval remains available.
        vector_store = PgVectorStore()
        added = vector_store.add_chunks(chunks, index_version=version.pk)
        IndexingJob.objects.filter(pk=job.pk).update(progress=85)
        smoke_query = str(chunks[0]["text"])[:500]
        smoke_results = vector_store.search(
            smoke_query,
            top_k=1,
            scripture_filter=scripture.name,
            index_versions=[version.pk],
        )
        qualified = (
            added == len(chunks)
            and added > 0
            and len(source_manifest) == len(pdf_files)
            and bool(smoke_results)
            and smoke_results[0]["score"] >= settings.RAG_MIN_SIMILARITY
        )
        qualification = {
            "expected_chunks": len(chunks),
            "stored_chunks": added,
            "volume_count": len(source_manifest),
            "retrieval_smoke": bool(smoke_results),
            "retrieval_score": smoke_results[0]["score"] if smoke_results else 0.0,
            "threshold": settings.RAG_MIN_SIMILARITY,
        }
        if not qualified:
            version.status = ScriptureIndexVersion.Status.FAILED
            version.failure_code = INDEX_FAILURE_QUALIFICATION
            version.qualification = qualification
            version.save(update_fields=["status", "failure_code", "qualification"])
            raise RuntimeError(INDEX_FAILURE_QUALIFICATION)
        version.status = ScriptureIndexVersion.Status.QUALIFIED
        version.chunk_count = added
        version.qualification = qualification
        version.qualified_at = timezone.now()
        version.save(
            update_fields=[
                "status",
                "chunk_count",
                "qualification",
                "qualified_at",
            ]
        )

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
            previous_version_id = scripture.active_index_version_id
            if previous_version_id:
                ScriptureIndexVersion.objects.filter(
                    pk=previous_version_id,
                    status=ScriptureIndexVersion.Status.ACTIVE,
                ).update(status=ScriptureIndexVersion.Status.RETIRED)
            version.status = ScriptureIndexVersion.Status.ACTIVE
            version.activated_at = timezone.now()
            version.save(update_fields=["status", "activated_at"])
            scripture.total_volumes = len(volumes)
            scripture.total_pages = sum(volume[2] for volume in volumes)
            scripture.is_indexed = True
            scripture.last_indexed_at = timezone.now()
            scripture.active_index_version = version
            scripture.save(
                update_fields=[
                    "total_volumes",
                    "total_pages",
                    "is_indexed",
                    "last_indexed_at",
                    "active_index_version",
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
        retained_previous_ids = list(
            ScriptureIndexVersion.objects.filter(
                scripture=scripture,
                status=ScriptureIndexVersion.Status.RETIRED,
            )
            .order_by("-activated_at")
            .values_list("pk", flat=True)[:1]
        )
        stale_versions = ScriptureIndexVersion.objects.filter(
            scripture=scripture,
            status=ScriptureIndexVersion.Status.RETIRED,
        ).exclude(pk__in=retained_previous_ids)
        stale_ids = list(stale_versions.values_list("pk", flat=True))
        if stale_ids:
            DocumentChunk.objects.filter(index_version__in=stale_ids).delete()
            stale_versions.delete()
    except Exception as exc:
        logger.exception("Scripture indexing failed for job %s", job_id)
        failure_code = (
            INDEX_FAILURE_QUALIFICATION
            if str(exc) == INDEX_FAILURE_QUALIFICATION
            else INDEX_FAILURE_BUILD
        )
        ScriptureIndexVersion.objects.filter(
            pk=version.pk,
            status__in=[
                ScriptureIndexVersion.Status.BUILDING,
                ScriptureIndexVersion.Status.QUALIFIED,
            ],
        ).update(
            status=ScriptureIndexVersion.Status.FAILED,
            failure_code=failure_code,
        )
        IndexingJob.objects.filter(pk=job.pk).update(
            status=IndexingJob.Status.FAILED,
            error_message=failure_code,
            finished_at=timezone.now(),
        )
        raise
