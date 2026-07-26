"""URL routes for provider-neutral model platform APIs."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from llm.views import (
    ModelConnectionViewSet,
    ModelProfileViewSet,
    UserModelPreferenceViewSet,
)

app_name = "llm"

router = DefaultRouter()
router.register("connections", ModelConnectionViewSet, basename="model-connection")
router.register("profiles", ModelProfileViewSet, basename="model-profile")
router.register("preferences", UserModelPreferenceViewSet, basename="model-preference")

urlpatterns = [
    path("", include(router.urls)),
]
