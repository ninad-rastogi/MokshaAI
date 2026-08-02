"""URL configuration for the chat app."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from chat.views import ChatViewSet

app_name = "chat"

router = DefaultRouter()
router.register("", ChatViewSet, basename="chat")

urlpatterns = [
    path("", include(router.urls)),
]
