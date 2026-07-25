"""Custom SimpleJWT serializers for email-based authentication."""

from typing import cast

from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom token serializer that accepts email instead of username."""

    username_field = User.USERNAME_FIELD

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Replace 'username' field with 'email' field
        self.fields.pop("username", None)
        self.fields["email"] = serializers.EmailField()

    def validate(self, attrs):
        """Validate using email instead of username."""
        email = attrs.get("email")
        password = attrs.get("password")

        if email and password:
            user = authenticate(
                request=self.context.get("request"),
                username=email,  # SimpleJWT uses 'username' param internally
                password=password,
            )

            if not user:
                raise serializers.ValidationError(
                    "No active account found with the given credentials.",
                    code="authorization",
                )

            if not user.is_active:
                raise serializers.ValidationError(
                    "User account is disabled.",
                    code="authorization",
                )

        else:
            raise serializers.ValidationError(
                'Must include "email" and "password".',
                code="authorization",
            )

        refresh = cast(RefreshToken, self.get_token(user))

        data = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

        return data
