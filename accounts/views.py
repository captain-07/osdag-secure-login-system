from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import RegisterSerializer, UserSerializer


# =============================================================================
# CONFIGURATION
# =============================================================================

User = get_user_model()

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


# =============================================================================
# HELPERS
# =============================================================================

def generic_auth_error():
    """
    Return the same error for all authentication failures.

    This prevents attackers from determining whether an email
    exists in the database.
    """
    return Response(
        {"detail": "Invalid email or password."},
        status=status.HTTP_401_UNAUTHORIZED,
    )


# =============================================================================
# REGISTRATION
# =============================================================================

class RegisterView(generics.CreateAPIView):
    """
    Register a new user.
    """

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


# =============================================================================
# LOGIN
# =============================================================================

class LoginView(APIView):
    """
    Authenticate a user and issue JWT access + refresh tokens.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email", "")
        password = request.data.get("password", "")

        # ---------------------------------------------------------------------
        # Find user
        # ---------------------------------------------------------------------

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Do not reveal whether the email exists.
            return generic_auth_error()

        # ---------------------------------------------------------------------
        # Check account lockout
        # ---------------------------------------------------------------------

        if user.is_locked():
            # Return the same response as other authentication failures.
            return generic_auth_error()

        # ---------------------------------------------------------------------
        # Validate password
        # ---------------------------------------------------------------------

        if not user.check_password(password):
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

        # ---------------------------------------------------------------------
        # Successful login
        # ---------------------------------------------------------------------

        user.failed_login_attempts = 0
        user.locked_until = None

        user.save(
            update_fields=[
                "failed_login_attempts",
                "locked_until",
            ]
        )

        # Generate JWT tokens.
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


# =============================================================================
# LOGOUT
# =============================================================================

class LogoutView(APIView):
    """
    Invalidate the current access token and refresh token.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # ---------------------------------------------------------------------
        # Blocklist the current access token in Redis
        # ---------------------------------------------------------------------

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

        # ---------------------------------------------------------------------
        # Blacklist the refresh token
        # ---------------------------------------------------------------------

        refresh_str = request.data.get("refresh")

        if refresh_str:
            try:
                RefreshToken(refresh_str).blacklist()
            except TokenError:
                # Already invalid or blacklisted.
                # Logout should remain idempotent.
                pass

        return Response(status=status.HTTP_205_RESET_CONTENT)


# =============================================================================
# CURRENT USER
# =============================================================================

class MeView(APIView):
    """
    Return the profile of the currently authenticated user.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # request.user comes from the validated JWT.
        # No user ID/email is accepted from the client.
        return Response(
            UserSerializer(request.user).data,
            status=status.HTTP_200_OK,
        )