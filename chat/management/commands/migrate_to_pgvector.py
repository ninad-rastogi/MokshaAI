"""
Management command to migrate embeddings to pgvector format.

Usage:
    python manage.py migrate_to_pgvector

This command verifies the native pgvector implementation.
"""

import logging

from django.core.management.base import BaseCommand
from django.db import connection

from chat.models import DocumentChunk

logger = logging.getLogger("chat.management.migrate_to_pgvector")


class Command(BaseCommand):
    help = "Verify pgvector is installed and native embeddings are available"

    def handle(self, *args, **options):
        self.stdout.write("Checking native pgvector embeddings...")

        # Check current state
        total_chunks = DocumentChunk.objects.count()
        chunks_with_embedding = DocumentChunk.objects.exclude(embedding=None).count()
        chunks_without_embedding = total_chunks - chunks_with_embedding

        self.stdout.write(f"Total chunks: {total_chunks}")
        self.stdout.write(f"Chunks with embeddings: {chunks_with_embedding}")
        self.stdout.write(f"Chunks without embeddings: {chunks_without_embedding}")

        # Check pgvector extension availability.
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector';")
            has_pgvector = cursor.fetchone() is not None

        if not has_pgvector:
            self.stdout.write(
                self.style.WARNING(
                    "pgvector extension not installed. Use the pgvector Docker image "
                    "or enable the extension before running the application."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS("pgvector extension and native embeddings ready.")
        )
