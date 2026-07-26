"""
URL configuration for Moksha AI project.
"""

from django.contrib import admin
from django.urls import include, path

from chat.views import RunViewSet

run_detail = RunViewSet.as_view({"get": "retrieve"})
run_cancel = RunViewSet.as_view({"post": "cancel"})
run_events = RunViewSet.as_view({"get": "events"})

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("users.urls")),
    path("api/chat/", include("chat.urls")),
    path("api/scriptures/", include("scriptures.urls")),
    path("api/models/", include("llm.urls")),
    path("api/v1/auth/", include(("users.urls", "users"), namespace="users-v1")),
    path("api/v1/chats/", include(("chat.urls", "chat"), namespace="chat-v1")),
    path("api/v1/runs/<uuid:pk>/", run_detail, name="generation-run-detail"),
    path(
        "api/v1/runs/<uuid:pk>/cancel/",
        run_cancel,
        name="generation-run-cancel",
    ),
    path(
        "api/v1/runs/<uuid:pk>/events/",
        run_events,
        name="generation-run-events",
    ),
    path("api/v1/models/", include(("llm.urls", "llm"), namespace="llm-v1")),
    path(
        "api/v1/scriptures/",
        include(("scriptures.urls", "scriptures"), namespace="scriptures-v1"),
    ),
]
