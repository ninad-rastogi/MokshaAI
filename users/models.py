"""Custom user model for Moksha AI."""

from typing import Any

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager["User"]):
    """Custom user manager that uses email instead of username."""

    def create_user(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom user model using email as the primary identifier."""

    email = models.EmailField(unique=True)
    username = None  # type: ignore[assignment]  # Email replaces username.
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    spiritual_name = models.CharField(max_length=100, blank=True)
    preferred_theme = models.CharField(max_length=20, default="system")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()  # type: ignore[misc, assignment]

    def __str__(self) -> str:
        return self.email
