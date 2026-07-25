"""URL configuration for the chat app."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from chat.views import ChatViewSet, RunViewSet

app_name = "chat"

router = DefaultRouter()
router.register("runs", RunViewSet, basename="run")
router.register("", ChatViewSet, basename="chat")

urlpatterns = [
    path("", include(router.urls)),
]
