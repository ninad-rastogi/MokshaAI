"""Seed the installed local Ollama profile as selectable default."""

from django.conf import settings
from django.db import migrations


def seed_builtin_ollama(apps, schema_editor):
    ModelConnection = apps.get_model("llm", "ModelConnection")
    ModelProfile = apps.get_model("llm", "ModelProfile")
    connection, _ = ModelConnection.objects.get_or_create(
        user=None,
        name="Local Ollama",
        dialect="builtin_ollama",
        defaults={"status": "connected"},
    )
    ModelProfile.objects.filter(is_admin_default=True).exclude(
        name="Moksha Qwen3 local"
    ).update(is_admin_default=False)
    ModelProfile.objects.get_or_create(
        name="Moksha Qwen3 local",
        defaults={
            "connection": connection,
            "model_id": getattr(
                settings, "OLLAMA_MODEL", "moksha-qwen3:4b-instruct-q3km"
            ),
            "is_enabled": True,
            "is_admin_default": True,
            "context_window": 8192,
            "max_output_tokens": 1024,
            "temperature": 0.2,
            "concurrency_limit": 1,
        },
    )


def unseed_builtin_ollama(apps, schema_editor):
    ModelProfile = apps.get_model("llm", "ModelProfile")
    ModelProfile.objects.filter(name="Moksha Qwen3 local").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("llm", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_builtin_ollama, unseed_builtin_ollama),
    ]
