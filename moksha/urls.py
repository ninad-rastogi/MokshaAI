"""
URL configuration for Moksha AI project.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("users.urls")),
    path("api/chat/", include("chat.urls")),
    path("api/scriptures/", include("scriptures.urls")),
    path("api/models/", include("llm.urls")),
    path("api/v1/auth/", include(("users.urls", "users"), namespace="users-v1")),
    path("api/v1/chats/", include(("chat.urls", "chat"), namespace="chat-v1")),
    path("api/v1/models/", include(("llm.urls", "llm"), namespace="llm-v1")),
    path(
        "api/v1/scriptures/",
        include(("scriptures.urls", "scriptures"), namespace="scriptures-v1"),
    ),
]
