"""Views for the users app."""

import secrets
import shutil

import requests
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.middleware.csrf import get_token
from redis import Redis
from redis.exceptions import RedisError
from rest_framework import generics, permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import CharField, EmailField, Serializer
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from users.serializers import RegisterSerializer, UserSerializer

User = get_user_model()


class RefreshThrottle(AnonRateThrottle):
    scope = "refresh"


class LoginView(TokenObtainPairView):
    throttle_classes: list[type[AnonRateThrottle]] = []


class RefreshView(TokenRefreshView):
    throttle_classes = [RefreshThrottle]


class SessionLoginSerializer(Serializer):
    """Validate browser session login credentials."""

    email = EmailField()
    password = CharField(style={"input_type": "password"})


class CsrfTokenView(APIView):
    """Issue a CSRF cookie for browser clients."""

    permission_classes = [permissions.AllowAny]

    def get(self, request: Request) -> Response:
        return Response({"csrfToken": get_token(request._request)})


class SessionLoginView(APIView):
    """Create a Django session for first-party browser clients."""

    permission_classes = [permissions.AllowAny]
    throttle_classes: list[type[AnonRateThrottle]] = []

    def post(self, request: Request) -> Response:
        serializer = SessionLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response(
                {"error": "invalid_credentials"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request._request, user)
        return Response(UserSerializer(user).data)


class SessionStatusView(APIView):
    """Report browser session state without logging normal anonymous visits."""

    permission_classes = [permissions.AllowAny]

    def get(self, request: Request) -> Response:
        if not request.user.is_authenticated:
            return Response({"authenticated": False, "user": None})
        return Response(
            {
                "authenticated": True,
                "user": UserSerializer(request.user).data,
            }
        )


class SessionLogoutView(APIView):
    """Clear a Django browser session."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request) -> Response:
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisterView(generics.CreateAPIView):
    """Register a new user and return user data."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes: list[type[AnonRateThrottle]] = []

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request._request, user)
        return Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


class ProfileView(APIView):
    """Get or update current user profile."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(UserSerializer(request.user).data)

    def put(self, request: Request) -> Response:
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class HealthCheckView(APIView):
    """Health check endpoint (no auth required)."""

    permission_classes = [permissions.AllowAny]

    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


class ReadinessCheckView(APIView):
    """Check dependencies required to accept production traffic."""

    permission_classes = [permissions.AllowAny]

    def get(self, request: Request) -> Response:
        database_ready = False
        redis_ready = False
        ollama_ready = False
        embedding_ready = False
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            database_ready = True
        except DatabaseError:
            database_ready = False
        try:
            redis = Redis.from_url(
                settings.CELERY_BROKER_URL,
                socket_connect_timeout=1,
            )
            redis.ping()
            redis.close()
            redis_ready = True
        except RedisError:
            redis_ready = False
        session = requests.Session()
        session.trust_env = False
        try:
            response = session.get(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags",
                timeout=(1, 2),
                stream=True,
            )
            ollama_ready = response.ok
            response.close()
        except requests.RequestException:
            pass
        try:
            response = session.get(
                f"{settings.EMBEDDING_SERVICE_URL.rstrip('/')}/ready",
                timeout=(1, 3),
                stream=True,
            )
            embedding_ready = response.ok
            response.close()
        except requests.RequestException:
            pass
        finally:
            session.close()
        try:
            disk_ready = (
                shutil.disk_usage(settings.DATA_DIR).free
                >= settings.DISK_MIN_FREE_BYTES
            )
        except OSError:
            disk_ready = False
        dependencies = {
            "database": database_ready,
            "redis": redis_ready,
            "ollama": ollama_ready,
            "embedding": embedding_ready,
            "disk": disk_ready,
        }
        return Response(
            {
                "status": "ready" if all(dependencies.values()) else "unavailable",
                **dependencies,
            },
            status=(
                status.HTTP_200_OK
                if all(dependencies.values())
                else status.HTTP_503_SERVICE_UNAVAILABLE
            ),
        )


class MetricsView(APIView):
    """Expose bounded Prometheus metrics to staff or configured scrapers."""

    permission_classes = [permissions.AllowAny]

    def get(self, request: Request) -> HttpResponse:
        configured = settings.METRICS_TOKEN
        supplied = request.headers.get("X-Metrics-Token", "")
        authorized = bool(
            getattr(request.user, "is_staff", False)
            or (
                configured and supplied and secrets.compare_digest(configured, supplied)
            )
        )
        if not authorized:
            return HttpResponse(status=403)

        from chat.models import GenerationRun
        from llm.models import ModelInstallationJob
        from scriptures.models import IndexingJob

        lines = [
            "# HELP moksha_generation_runs Generation runs by durable state.",
            "# TYPE moksha_generation_runs gauge",
        ]
        for state, _label in GenerationRun.State.choices:
            count = GenerationRun.objects.filter(state=state).count()
            lines.append(f'moksha_generation_runs{{state="{state}"}} {count}')
        lines.extend(
            [
                "# HELP moksha_indexing_jobs Active indexing jobs.",
                "# TYPE moksha_indexing_jobs gauge",
                (
                    "moksha_indexing_jobs "
                    f"{IndexingJob.objects.filter(status__in=['PENDING', 'RUNNING']).count()}"
                ),
                "# HELP moksha_model_installations Active model installations.",
                "# TYPE moksha_model_installations gauge",
                (
                    "moksha_model_installations "
                    f"{ModelInstallationJob.objects.filter(status__in=['pending', 'running']).count()}"
                ),
            ]
        )
        return HttpResponse(
            "\n".join(lines) + "\n",
            content_type="text/plain; version=0.0.4; charset=utf-8",
        )
