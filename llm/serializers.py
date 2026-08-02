"""Serializers for provider-neutral model platform objects."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from llm.models import (
    ModelCatalogRelease,
    ModelConnection,
    ModelInstallationJob,
    ModelProfile,
    UserModelPreference,
)


class ModelConnectionSerializer(serializers.ModelSerializer):
    """Sanitized connection status. Secrets are never serialized."""

    class Meta:
        model = ModelConnection
        fields = (
            "id",
            "name",
            "dialect",
            "endpoint_url",
            "status",
            "sanitized_detail",
            "remote_data_consent_at",
            "last_checked_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ModelConnectionCreateSerializer(serializers.Serializer):
    """Create a user BYOK endpoint plus one selectable profile."""

    name = serializers.CharField(max_length=120)
    dialect = serializers.ChoiceField(
        choices=[
            ModelConnection.Dialect.OPENAI_COMPATIBLE,
            ModelConnection.Dialect.OLLAMA_COMPATIBLE,
        ]
    )
    endpoint_url = serializers.URLField(max_length=500)
    model_id = serializers.CharField(max_length=180)
    api_key = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        write_only=True,
        trim_whitespace=False,
    )
    remote_data_consent = serializers.BooleanField()

    def validate_remote_data_consent(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError("remote_data_consent_required")
        return value

    def create(self, validated_data: dict) -> ModelConnection:
        user = self.context["request"].user
        api_key = validated_data.pop("api_key", "")
        model_id = validated_data.pop("model_id")
        validated_data.pop("remote_data_consent", None)
        connection = ModelConnection(
            user=user,
            status=ModelConnection.Status.DISCONNECTED,
            remote_data_consent_at=timezone.now(),
            **validated_data,
        )
        try:
            connection.full_clean()
            connection.save()
            if api_key:
                connection.set_api_key(api_key)
                connection.save(
                    update_fields=[
                        "api_key_nonce",
                        "encrypted_api_key",
                        "key_version",
                    ]
                )
        except DjangoValidationError as exc:
            detail = getattr(exc, "message_dict", None) or getattr(
                exc, "messages", ["invalid_connection"]
            )
            raise serializers.ValidationError(detail) from exc
        ModelProfile.objects.create(
            name=f"{connection.name} - {model_id} ({str(connection.pk)[:8]})",
            connection=connection,
            model_id=model_id,
            is_enabled=True,
            context_window=8192,
            max_output_tokens=1024,
            temperature=0.2,
            concurrency_limit=4,
        )
        return connection


class ModelConnectionProbeSerializer(serializers.Serializer):
    """Sanitized connection probe response."""

    status = serializers.CharField()
    detail = serializers.CharField()
    models = serializers.ListField(child=serializers.CharField())


class ModelProfileSerializer(serializers.ModelSerializer):
    """Selectable model profile."""

    connection_status = serializers.CharField(
        source="connection.status", read_only=True, default=""
    )
    connection_dialect = serializers.CharField(
        source="connection.dialect", read_only=True, default=""
    )

    class Meta:
        model = ModelProfile
        fields = (
            "id",
            "name",
            "model_id",
            "connection",
            "connection_status",
            "connection_dialect",
            "is_enabled",
            "is_admin_default",
            "context_window",
            "max_output_tokens",
            "temperature",
        )
        read_only_fields = fields


class UserModelPreferenceSerializer(serializers.ModelSerializer):
    """User model routing preference."""

    primary_profile_detail = ModelProfileSerializer(
        source="primary_profile", read_only=True
    )

    class Meta:
        model = UserModelPreference
        fields = (
            "primary_profile",
            "primary_profile_detail",
            "ordered_fallback_profile_ids",
            "updated_at",
        )
        read_only_fields = ("updated_at",)

    def validate_ordered_fallback_profile_ids(self, value: list[str]) -> list[str]:
        if not isinstance(value, list):
            raise serializers.ValidationError("fallbacks_must_be_ordered_list")
        if len(value) > 8:
            raise serializers.ValidationError("too_many_fallbacks")
        normalized = [str(item) for item in value]
        if len(set(normalized)) != len(normalized):
            raise serializers.ValidationError("duplicate_fallbacks")
        return normalized

    def validate(self, attrs: dict) -> dict:
        user = self.context["request"].user
        primary = attrs.get("primary_profile")
        fallback_ids = attrs.get("ordered_fallback_profile_ids", [])
        available_profiles = ModelProfile.objects.filter(
            Q(connection__user=user) | Q(connection__user=None),
            is_enabled=True,
        )
        if primary and not available_profiles.filter(pk=primary.pk).exists():
            raise serializers.ValidationError(
                {"primary_profile": "primary_model_unavailable"}
            )
        if primary and str(primary.pk) in fallback_ids:
            raise serializers.ValidationError(
                {"ordered_fallback_profile_ids": "primary_cannot_be_fallback"}
            )
        available_ids = {
            str(profile_id)
            for profile_id in available_profiles.filter(
                id__in=fallback_ids,
            ).values_list("id", flat=True)
        }
        if set(fallback_ids) != available_ids:
            raise serializers.ValidationError(
                {"ordered_fallback_profile_ids": "fallback_model_unavailable"}
            )
        return attrs


class ModelCatalogReleaseSerializer(serializers.ModelSerializer):
    """Public metadata from a verified catalog release."""

    entries = serializers.SerializerMethodField()

    class Meta:
        model = ModelCatalogRelease
        fields = (
            "version",
            "sequence",
            "issued_at",
            "expires_at",
            "active",
            "accepted_at",
            "entries",
        )
        read_only_fields = fields

    def get_entries(self, obj: ModelCatalogRelease) -> list[dict]:
        entries = obj.payload.get("entries", [])
        return entries if isinstance(entries, list) else []


class ModelInstallationJobSerializer(serializers.ModelSerializer):
    """Sanitized staff view of local model installation state."""

    class Meta:
        model = ModelInstallationJob
        fields = (
            "id",
            "model_profile",
            "status",
            "ollama_tag",
            "keep_source",
            "qualification",
            "error_code",
            "created_at",
            "started_at",
            "finished_at",
        )
        read_only_fields = fields


class ModelInstallationCreateSerializer(serializers.Serializer):
    """Accept only an entry from active verified catalog."""

    entry_id = serializers.SlugField(max_length=120)
    keep_source = serializers.BooleanField(default=False)
