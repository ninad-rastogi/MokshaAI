"""App configuration for scriptures."""

from django.apps import AppConfig


class ScripturesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "scriptures"
    verbose_name = "Scripture Management"
