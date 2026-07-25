from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("scriptures", "0002_volume_content_hash"),
    ]

    operations = [
        migrations.CreateModel(
            name="IndexingJob",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("RUNNING", "Running"),
                            ("SUCCEEDED", "Succeeded"),
                            ("FAILED", "Failed"),
                        ],
                        default="PENDING",
                        max_length=12,
                    ),
                ),
                ("progress", models.PositiveSmallIntegerField(default=0)),
                ("celery_task_id", models.CharField(blank=True, max_length=255)),
                ("error_message", models.TextField(blank=True)),
                ("chunks_indexed", models.PositiveIntegerField(default=0)),
                ("volumes_processed", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "requested_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="indexing_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "scripture",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="indexing_jobs",
                        to="scriptures.scripture",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
