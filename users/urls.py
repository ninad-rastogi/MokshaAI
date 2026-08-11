"""URL configuration for the users app."""

from django.urls import path

from users.views import (
    CsrfTokenView,
    HealthCheckView,
    LoginView,
    MetricsView,
    ProfileView,
    ReadinessCheckView,
    RefreshView,
    RegisterView,
    SessionLoginView,
    SessionLogoutView,
    SessionStatusView,
)

app_name = "users"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshView.as_view(), name="token-refresh"),
    path("csrf/", CsrfTokenView.as_view(), name="csrf"),
    path("session/", SessionStatusView.as_view(), name="session-status"),
    path("session/login/", SessionLoginView.as_view(), name="session-login"),
    path("session/logout/", SessionLogoutView.as_view(), name="session-logout"),
    path("me/", ProfileView.as_view(), name="profile"),
    path("health/", HealthCheckView.as_view(), name="health"),
    path("ready/", ReadinessCheckView.as_view(), name="ready"),
    path("metrics/", MetricsView.as_view(), name="metrics"),
]
