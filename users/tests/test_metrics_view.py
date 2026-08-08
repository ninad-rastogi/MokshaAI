"""Tests for metrics endpoint authorization."""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import override_settings
from rest_framework.test import APIRequestFactory

from users.views import MetricsView


@override_settings(METRICS_TOKEN="")
def test_metrics_forbidden_when_no_staff_user_or_token_configured():
    request = APIRequestFactory().get("/api/auth/metrics/")
    cast(Any, request).user = AnonymousUser()

    response = MetricsView.as_view()(request)

    assert response.status_code == 403


@override_settings(METRICS_TOKEN="expected-token")
def test_metrics_forbidden_when_token_does_not_match():
    request = APIRequestFactory().get(
        "/api/auth/metrics/",
        HTTP_X_METRICS_TOKEN="wrong-token",
    )
    cast(Any, request).user = AnonymousUser()

    response = MetricsView.as_view()(request)

    assert response.status_code == 403


@override_settings(METRICS_TOKEN="expected-token")
def test_metrics_allows_configured_scraper_token_without_user():
    request = APIRequestFactory().get(
        "/api/auth/metrics/",
        HTTP_X_METRICS_TOKEN="expected-token",
    )
    cast(Any, request).user = AnonymousUser()

    with (
        patch("chat.models.GenerationRun.objects.filter") as generation_filter,
        patch("scriptures.models.IndexingJob.objects.filter") as indexing_filter,
        patch("llm.models.ModelInstallationJob.objects.filter") as installation_filter,
    ):
        generation_filter.return_value.count.return_value = 2
        indexing_filter.return_value.count.return_value = 1
        installation_filter.return_value.count.return_value = 0
        response = MetricsView.as_view()(request)

    assert response.status_code == 200
    rendered = response.content.decode("utf-8")
    assert "moksha_generation_runs" in rendered
    assert "moksha_indexing_jobs 1" in rendered
    assert "moksha_model_installations 0" in rendered


@override_settings(METRICS_TOKEN="")
def test_metrics_allows_staff_user_without_scraper_token():
    request = APIRequestFactory().get("/api/auth/metrics/")
    staff = SimpleNamespace(
        is_active=True,
        is_authenticated=True,
        is_staff=True,
        pk=1,
    )
    cast(Any, request).user = staff

    with (
        patch("chat.models.GenerationRun.objects.filter") as generation_filter,
        patch("scriptures.models.IndexingJob.objects.filter") as indexing_filter,
        patch("llm.models.ModelInstallationJob.objects.filter") as installation_filter,
    ):
        generation_filter.return_value.count.return_value = 0
        indexing_filter.return_value.count.return_value = 0
        installation_filter.return_value.count.return_value = 0
        response = MetricsView.as_view()(request)

    assert response.status_code == 200
    assert response["Content-Type"] == "text/plain; version=0.0.4; charset=utf-8"
