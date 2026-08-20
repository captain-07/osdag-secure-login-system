from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import RegisterSerializer, UserSerializer
from .throttling import LoginRateThrottle, RegisterRateThrottle


User = get_user_model()

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


def generic_auth_error():
    """
    Return the same error for all authentication failures.

    Prevents attackers from determining whether an email
    exists in the database.
    """
    return Response(
        {"detail": "Invalid email or password."},
        status=status.HTTP_401_UNAUTHORIZED,
    )


class RegisterView(generics.CreateAPIView):
    """
    Register a new user.
    """

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterRateThrottle]


class LoginView(APIView):
    """
    Authenticate a user and issue JWT access + refresh tokens.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        email = request.data.get("email", "")
        password = request.data.get("password", "")

        with transaction.atomic():
            try:
                user = User.objects.select_for_update().get(email=email)
            except User.DoesNotExist:
                return generic_auth_error()

            if user.is_locked():
                return generic_auth_error()

            if not user.is_active:
                return generic_auth_error()

            if not user.check_password(password):
                if user.locked_until and user.locked_until <= timezone.now():
                    user.failed_login_attempts = 0
                    user.locked_until = None

                user.failed_login_attempts += 1

                if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                    user.locked_until = timezone.now() + LOCKOUT_DURATION

                user.save(
                    update_fields=[
                        "failed_login_attempts",
                        "locked_until",
                    ]
                )

                return generic_auth_error()

            user.failed_login_attempts = 0
            user.locked_until = None

            user.save(
                update_fields=[
                    "failed_login_attempts",
                    "locked_until",
                ]
            )

        refresh = RefreshToken.for_user(user)

        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        return Response(
            {
                "access": access_token,
                "refresh": refresh_token,

                "token": access_token,

                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    Invalidate the current access token and refresh token.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):

        access_token = request.auth
        jti = access_token["jti"]

        current_timestamp = int(timezone.now().timestamp())
        remaining_seconds = access_token["exp"] - current_timestamp

        if remaining_seconds > 0:
            cache.set(
                f"blocklist:{jti}",
                True,
                timeout=remaining_seconds,
            )

        refresh_str = request.data.get("refresh")

        if refresh_str:
            try:
                RefreshToken(refresh_str).blacklist()

            except TokenError:
                pass

        return Response(
            status=status.HTTP_205_RESET_CONTENT
        )


class MeView(APIView):
    """
    Return the profile of the currently authenticated user.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):

        return Response(
            UserSerializer(request.user).data,
            status=status.HTTP_200_OK,
        )