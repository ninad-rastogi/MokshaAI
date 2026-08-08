"""Use corpus/provider-neutral display name for built-in local model."""

from typing import ClassVar

from django.db import migrations

OLD_NAME = "Moksha Qwen3 local"
NEW_NAME = "Moksha local"


def rename_builtin_profile(apps, schema_editor):
    ModelConnection = apps.get_model("llm", "ModelConnection")
    ModelProfile = apps.get_model("llm", "ModelProfile")
    builtin_connections = ModelConnection.objects.filter(dialect="builtin_ollama")
    ModelProfile.objects.filter(
        connection__in=builtin_connections,
        name=OLD_NAME,
    ).update(name=NEW_NAME)


def restore_builtin_profile_name(apps, schema_editor):
    ModelConnection = apps.get_model("llm", "ModelConnection")
    ModelProfile = apps.get_model("llm", "ModelProfile")
    builtin_connections = ModelConnection.objects.filter(dialect="builtin_ollama")
    ModelProfile.objects.filter(
        connection__in=builtin_connections,
        name=NEW_NAME,
    ).update(name=OLD_NAME)


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("llm", "0003_modelcatalogrelease"),
    ]

    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(rename_builtin_profile, restore_builtin_profile_name),
    ]
