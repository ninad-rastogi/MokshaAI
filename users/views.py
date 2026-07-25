"""Views for the users app."""

import requests
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.conf import settings
from django.middleware.csrf import get_token
from django.db import connection
from redis import Redis
from rest_framework import generics, permissions, status
from rest_framework.serializers import CharField, EmailField, Serializer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from users.serializers import RegisterSerializer, UserSerializer

User = get_user_model()


class RegistrationThrottle(AnonRateThrottle):
    scope = "registration"


class LoginThrottle(AnonRateThrottle):
    scope = "login"


class RefreshThrottle(AnonRateThrottle):
    scope = "refresh"


class LoginView(TokenObtainPairView):
    throttle_classes = [LoginThrottle]


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
        return Response({"csrfToken": get_token(request)})


class SessionLoginView(APIView):
    """Create a Django session for first-party browser clients."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginThrottle]

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
        login(request, user)
        return Response(UserSerializer(user).data)


class SessionLogoutView(APIView):
    """Clear a Django browser session."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request) -> Response:
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisterView(generics.CreateAPIView):
    """Register a new user and return user data."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegistrationThrottle]

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
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
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            database_ready = True
        except Exception:
            pass
        try:
            Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=1).ping()
            redis_ready = True
        except Exception:
            pass
        try:
            response = requests.get(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=2
            )
            ollama_ready = response.ok
        except requests.RequestException:
            pass
        dependencies = {
            "database": database_ready,
            "redis": redis_ready,
            "ollama": ollama_ready,
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
