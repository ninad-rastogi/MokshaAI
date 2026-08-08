"""Tests for metrics endpoint authorization."""

from typing import Any, cast

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
