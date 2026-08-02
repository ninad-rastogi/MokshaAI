"""Models for provider-neutral model connections and local model platform."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from llm.security import (
    aad_for_connection,
    active_key_version,
    decrypt_secret,
    encrypt_secret,
    validate_public_https_endpoint,
)


class ModelConnection(models.Model):
    """A user or admin-owned provider endpoint with encrypted BYOK material."""

    class Dialect(models.TextChoices):
        OPENAI_COMPATIBLE = "openai_compatible", "OpenAI-compatible"
        OLLAMA_COMPATIBLE = "ollama_compatible", "Ollama-compatible"
        BUILTIN_OLLAMA = "builtin_ollama", "Built-in Ollama"

    class Status(models.TextChoices):
        DISCONNECTED = "disconnected", "Disconnected"
        CHECKING = "checking", "Checking"
        CONNECTED = "connected", "Connected"
        DEGRADED = "degraded", "Degraded"
        AUTH_INVALID = "auth_invalid", "Auth invalid"
        ENDPOINT_INVALID = "endpoint_invalid", "Endpoint invalid"
        UNREACHABLE = "unreachable", "Unreachable"
        RATE_LIMITED = "rate_limited", "Rate limited"
        QUOTA_LIMITED = "quota_limited", "Quota limited"
        MODEL_UNAVAILABLE = "model_unavailable", "Model unavailable"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="model_connections",
    )
    name = models.CharField(max_length=120)
    dialect = models.CharField(max_length=40, choices=Dialect.choices)
    endpoint_url = models.URLField(max_length=500, blank=True)
    status = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.DISCONNECTED,
        db_index=True,
    )
    sanitized_detail = models.CharField(max_length=240, blank=True)
    dns_pins = models.JSONField(default=list, blank=True)
    remote_data_consent_at = models.DateTimeField(null=True, blank=True)
    encrypted_api_key = models.TextField(blank=True)
    api_key_nonce = models.CharField(max_length=80, blank=True)
    key_version = models.PositiveSmallIntegerField(default=1)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["dialect", "status"]),
        ]

    def __str__(self) -> str:
        owner = self.user.email if self.user_id and self.user else "admin"
        return f"{self.name} ({owner})"

    @property
    def is_admin_connection(self) -> bool:
        return self.user_id is None

    def clean(self) -> None:
        if self.dialect == self.Dialect.BUILTIN_OLLAMA:
            return
        if not self.endpoint_url:
            raise ValidationError({"endpoint_url": "endpoint_required"})
        result = validate_public_https_endpoint(
            self.endpoint_url,
            allow_private=self.is_admin_connection,
            resolved_ips=self.dns_pins or None,
        )
        self.endpoint_url = result.normalized_url
        self.dns_pins = list(result.resolved_ips)
        if self.user_id and self.remote_data_consent_at is None:
            raise ValidationError(
                {"remote_data_consent_at": "remote_data_consent_required"}
            )

    def set_api_key(self, secret: str) -> None:
        if not self.user_id:
            raise ValidationError("user_required_for_byok_encryption")
        self.key_version = active_key_version()
        aad = aad_for_connection(self.user_id, str(self.pk), self.key_version)
        self.api_key_nonce, self.encrypted_api_key = encrypt_secret(
            secret,
            aad,
            key_version=self.key_version,
        )

    def get_api_key(self) -> str:
        if not self.user_id or not self.encrypted_api_key or not self.api_key_nonce:
            return ""
        aad = aad_for_connection(self.user_id, str(self.pk), self.key_version)
        return decrypt_secret(
            self.api_key_nonce,
            self.encrypted_api_key,
            aad,
            key_version=self.key_version,
        )

    def record_remote_consent(self) -> None:
        self.remote_data_consent_at = timezone.now()


class ModelProfile(models.Model):
    """A selectable model with immutable provider/model details per attempt."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    connection = models.ForeignKey(
        ModelConnection,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="profiles",
    )
    model_id = models.CharField(max_length=180)
    is_enabled = models.BooleanField(default=False, db_index=True)
    is_admin_default = models.BooleanField(default=False)
    context_window = models.PositiveIntegerField(default=8192)
    max_output_tokens = models.PositiveIntegerField(default=1024)
    temperature = models.FloatField(default=0.2)
    concurrency_limit = models.PositiveSmallIntegerField(default=1)
    qualification = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_admin_default"],
                condition=Q(is_admin_default=True),
                name="uniq_enabled_admin_default_model_profile",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} -> {self.model_id}"

    def snapshot(self) -> dict[str, object]:
        connection = self.connection
        return {
            "profile_id": str(self.pk),
            "profile_name": self.name,
            "model_id": self.model_id,
            "dialect": connection.dialect if connection else "",
            "connection_id": str(connection.pk) if connection else "",
            "connection_name": connection.name if connection else "",
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
        }


class UserModelPreference(models.Model):
    """User-selected primary model and ordered fallback profile IDs."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="model_preference",
    )
    primary_profile = models.ForeignKey(
        ModelProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="primary_for_users",
    )
    ordered_fallback_profile_ids = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user.email} model preference"


class HardwareProfile(models.Model):
    """Host-side hardware scan result. Django containers never run scans."""

    schema_version = models.PositiveSmallIntegerField(default=1)
    source = models.CharField(max_length=80, default="whichllm")
    profile_hash = models.CharField(max_length=128, unique=True)
    whichllm_version = models.CharField(max_length=80, blank=True)
    catalog_version = models.CharField(max_length=80, blank=True)
    driver_fingerprint = models.CharField(max_length=160, blank=True)
    payload = models.JSONField(default=dict)
    recommendations = models.JSONField(default=list, blank=True)
    stale = models.BooleanField(default=False, db_index=True)
    scanned_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scanned_at"]

    def __str__(self) -> str:
        return f"{self.source} scan {self.profile_hash[:12]}"


class ModelCatalogRelease(models.Model):
    """Verified catalog release accepted through a staff-only refresh."""

    schema_version = models.PositiveSmallIntegerField()
    sequence = models.PositiveIntegerField(unique=True)
    version = models.CharField(max_length=80, unique=True)
    key_id = models.CharField(max_length=80)
    catalog_hash = models.CharField(max_length=64, unique=True)
    signature = models.CharField(max_length=160)
    payload = models.JSONField()
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    active = models.BooleanField(default=False, db_index=True)
    accepted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sequence"]

    def __str__(self) -> str:
        return f"{self.version} ({self.sequence})"


class ModelInstallationJob(models.Model):
    """Staff-triggered local model install/qualification job."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="model_installation_jobs",
    )
    model_profile = models.ForeignKey(
        ModelProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="installation_jobs",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    active_lock = models.BooleanField(default=True, editable=False)
    catalog_entry = models.JSONField(default=dict)
    source_sha256 = models.CharField(max_length=64)
    source_size = models.PositiveBigIntegerField()
    import_path = models.CharField(max_length=500, blank=True)
    ollama_tag = models.CharField(max_length=180, blank=True)
    keep_source = models.BooleanField(default=False)
    qualification = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["active_lock"],
                condition=Q(status__in=["pending", "running"]),
                name="uniq_active_model_installation_job",
            )
        ]

    def __str__(self) -> str:
        return f"{self.status} install {self.source_sha256[:12]}"
