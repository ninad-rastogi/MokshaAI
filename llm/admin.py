"""Admin configuration for the model platform."""

from django.contrib import admin

from llm.models import (
    HardwareProfile,
    ModelConnection,
    ModelInstallationJob,
    ModelProfile,
    UserModelPreference,
)


@admin.register(ModelConnection)
class ModelConnectionAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "dialect", "status", "last_checked_at")
    list_filter = ("dialect", "status", "created_at")
    search_fields = ("name", "user__email", "endpoint_url")
    readonly_fields = (
        "id",
        "encrypted_api_key",
        "api_key_nonce",
        "dns_pins",
        "created_at",
        "updated_at",
    )


@admin.register(ModelProfile)
class ModelProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "model_id", "connection", "is_enabled", "is_admin_default")
    list_filter = ("is_enabled", "is_admin_default", "connection__dialect")
    search_fields = ("name", "model_id", "connection__name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(UserModelPreference)
class UserModelPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "primary_profile", "updated_at")
    search_fields = ("user__email", "primary_profile__name")


@admin.register(HardwareProfile)
class HardwareProfileAdmin(admin.ModelAdmin):
    list_display = ("source", "profile_hash", "stale", "scanned_at")
    list_filter = ("source", "stale", "schema_version")
    search_fields = ("profile_hash", "whichllm_version", "catalog_version")
    readonly_fields = ("created_at",)


@admin.register(ModelInstallationJob)
class ModelInstallationJobAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "created_by", "ollama_tag", "created_at")
    list_filter = ("status", "keep_source", "created_at")
    search_fields = ("id", "created_by__email", "ollama_tag", "source_sha256")
    readonly_fields = ("id", "created_at", "started_at", "finished_at")
