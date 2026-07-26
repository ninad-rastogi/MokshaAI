"""Serializers for the users app."""

from rest_framework import serializers

from users.models import User


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user profile."""

    class Meta:
        model = User
        fields = ("id", "email", "spiritual_name", "created_at")
        read_only_fields = ("id", "created_at")


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""

    password = serializers.CharField(
        write_only=True, min_length=8, style={"input_type": "password"}
    )
    password_confirm = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = ("email", "password", "password_confirm", "spiritual_name")
        extra_kwargs = {"email": {"validators": []}}

    def validate_email(self, email: str) -> str:
        normalized_email = User.objects.normalize_email(email)
        if User.objects.filter(email__iexact=normalized_email).exists():
            raise serializers.ValidationError(
                "Account already exists. Sign in instead."
            )
        return normalized_email

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data: dict) -> User:
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            spiritual_name=validated_data.get("spiritual_name", ""),
        )
        return user
