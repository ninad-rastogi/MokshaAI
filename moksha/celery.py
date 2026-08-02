"""Celery application for long-running Moksha AI work."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moksha.settings")

app = Celery("moksha", include=["moksha.tasks"])
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
