"""URL configuration for the scriptures app."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from scriptures.views import IndexingJobViewSet, ScriptureViewSet

app_name = "scriptures"

router = DefaultRouter()
router.register("indexing-jobs", IndexingJobViewSet, basename="indexing-job")
router.register("", ScriptureViewSet, basename="scripture")

urlpatterns = [
    path("", include(router.urls)),
]
