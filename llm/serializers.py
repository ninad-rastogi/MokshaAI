"""Serializers for provider-neutral model platform objects."""

from rest_framework import serializers

from llm.models import ModelConnection, ModelProfile, UserModelPreference


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

    class Meta:
        model = UserModelPreference
        fields = (
            "primary_profile",
            "ordered_fallback_profile_ids",
            "updated_at",
        )
        read_only_fields = ("updated_at",)

    def validate_ordered_fallback_profile_ids(self, value: list[str]) -> list[str]:
        if not isinstance(value, list):
            raise serializers.ValidationError("fallbacks_must_be_ordered_list")
        if len(value) > 8:
            raise serializers.ValidationError("too_many_fallbacks")
        return [str(item) for item in value]
