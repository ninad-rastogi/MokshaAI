"""
Management command to auto-discover and index scripture PDFs.

Usage:
    python manage.py discover_scriptures
    python manage.py discover_scriptures --scripture "Collection Name"
    python manage.py discover_scriptures --force
    python manage.py discover_scriptures --resume-running
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from scriptures.models import IndexingJob, Scripture
from scriptures.tasks import index_scripture

logger = logging.getLogger("chat.management.discover")


class Command(BaseCommand):
    help = "Auto-discover and index scripture PDFs from data/docs/"

    def add_arguments(self, parser):
        parser.add_argument(
            "--scripture",
            type=str,
            help="Re-index a specific scripture by name",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force re-indexing even if already indexed",
        )
        parser.add_argument(
            "--resume-running",
            action="store_true",
            help="Resume a RUNNING checkpoint after confirming its worker is stopped",
        )

    def handle(self, *args, **options):
        docs_dir = settings.DOCS_DIR
        if not docs_dir.exists():
            raise CommandError(f"Docs directory not found: {docs_dir}")

        # This command deliberately executes the same task synchronously so it
        # remains suitable for one-off operational runs and CI automation.
        requested_names = (
            [options["scripture"]]
            if options.get("scripture")
            else [
                item.name
                for item in sorted(
                    docs_dir.iterdir(), key=lambda path: path.name.casefold()
                )
                if item.is_dir()
                and not item.is_symlink()
                and any(
                    path.is_file() and not path.is_symlink()
                    for path in item.rglob("*.pdf")
                )
            ]
        )
        if not requested_names:
            self.stdout.write(self.style.WARNING("No scriptures found in data/docs/"))
            return
        operator = get_user_model().objects.filter(is_staff=True).first()
        if not operator:
            raise CommandError("Create a staff user before running scripture indexing.")
        for scripture_name in requested_names:
            scripture_path = docs_dir / scripture_name
            if not scripture_path.exists():
                raise CommandError(f"Scripture not found: {scripture_name}")
            scripture, _ = Scripture.objects.get_or_create(
                name=scripture_name, defaults={"folder_path": str(scripture_path)}
            )
            if scripture.folder_path != str(scripture_path):
                scripture.folder_path = str(scripture_path)
                scripture.save(update_fields=["folder_path"])
            if scripture.is_indexed and not options["force"]:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped {scripture_name}: already indexed (use --force to rebuild)"
                    )
                )
                continue
            active_job = IndexingJob.objects.filter(
                scripture=scripture,
                status__in=[IndexingJob.Status.PENDING, IndexingJob.Status.RUNNING],
            ).first()
            if (
                active_job
                and active_job.status == IndexingJob.Status.RUNNING
                and not options["resume_running"]
            ):
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped {scripture_name}: indexing job {active_job.pk} "
                        "is already running"
                    )
                )
                continue
            job = active_job or IndexingJob.objects.create(
                scripture=scripture,
                requested_by=operator,
            )
            index_scripture.apply(args=[job.pk], throw=True)
            job.refresh_from_db()
            if job.status != IndexingJob.Status.SUCCEEDED:
                raise CommandError(
                    job.error_message or f"Indexing {scripture_name} failed"
                )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Indexed {job.chunks_indexed} chunks from {scripture_name}"
                )
            )
