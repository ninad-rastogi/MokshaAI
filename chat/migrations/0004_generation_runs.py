import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0003_native_pgvector_and_sources"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GenerationRun",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("idempotency_key", models.CharField(max_length=255)),
                ("prompt", models.TextField()),
                ("model_profile", models.CharField(blank=True, max_length=120)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="queued",
                        max_length=20,
                    ),
                ),
                ("stream_key", models.CharField(max_length=255, unique=True)),
                ("last_event_id", models.CharField(blank=True, max_length=64)),
                ("final_text", models.TextField(blank=True)),
                ("final_sources", models.JSONField(blank=True, default=list)),
                ("error_code", models.CharField(blank=True, max_length=80)),
                ("queued_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "assistant_message",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="generation_assistant_runs",
                        to="chat.message",
                    ),
                ),
                (
                    "chat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="runs",
                        to="chat.chat",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="generation_runs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user_message",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="generation_user_runs",
                        to="chat.message",
                    ),
                ),
            ],
            options={
                "ordering": ["-queued_at"],
            },
        ),
        migrations.CreateModel(
            name="GenerationAttempt",
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
                ("attempt_number", models.PositiveSmallIntegerField()),
                ("provider", models.CharField(max_length=80)),
                ("model", models.CharField(max_length=160)),
                ("model_snapshot", models.JSONField(blank=True, default=dict)),
                (
                    "outcome",
                    models.CharField(
                        choices=[
                            ("started", "Started"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="started",
                        max_length=20,
                    ),
                ),
                ("error_code", models.CharField(blank=True, max_length=80)),
                ("usage", models.JSONField(blank=True, default=dict)),
                ("cost", models.JSONField(blank=True, default=dict)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attempts",
                        to="chat.generationrun",
                    ),
                ),
            ],
            options={
                "ordering": ["attempt_number"],
            },
        ),
        migrations.AddConstraint(
            model_name="generationrun",
            constraint=models.UniqueConstraint(
                fields=("chat", "idempotency_key"),
                name="uniq_generation_run_chat_idempotency",
            ),
        ),
        migrations.AddConstraint(
            model_name="generationattempt",
            constraint=models.UniqueConstraint(
                fields=("run", "attempt_number"),
                name="uniq_generation_attempt_number",
            ),
        ),
    ]
