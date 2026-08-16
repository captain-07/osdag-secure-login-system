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

    Prevents attackers from determining whether an email
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
    throttle_classes = [RegisterRateThrottle]


# =============================================================================
# LOGIN
# =============================================================================

class LoginView(APIView):
    """
    Authenticate a user and issue JWT access + refresh tokens.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        email = request.data.get("email", "")
        password = request.data.get("password", "")

        # The read-modify-write on failed_login_attempts below must be atomic:
        # two concurrent wrong-password requests could otherwise both read the
        # same counter and neither would trip the lockout threshold. Locking
        # the row for the duration of the transaction serializes them.
        with transaction.atomic():
            try:
                user = User.objects.select_for_update().get(email=email)
            except User.DoesNotExist:
                # Do not reveal whether the email exists.
                return generic_auth_error()

            # -----------------------------------------------------------------
            # Check account lockout
            # -----------------------------------------------------------------

            if user.is_locked():
                # Same response as other authentication failures.
                return generic_auth_error()

            # -----------------------------------------------------------------
            # Check account is active
            # -----------------------------------------------------------------

            if not user.is_active:
                # Same generic response — do not reveal the account state.
                return generic_auth_error()

            # -----------------------------------------------------------------
            # Validate password
            # -----------------------------------------------------------------

            if not user.check_password(password):
                # If a previous lockout has already expired, reset the attempt
                # budget first. Otherwise the stale count (which stays >= the
                # threshold while locked) would re-lock the account on a single
                # wrong guess the moment the window passes.
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

            # -----------------------------------------------------------------
            # Successful login
            # -----------------------------------------------------------------

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

        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        return Response(
            {
                "access": access_token,
                "refresh": refresh_token,

                # Alias used by the provided index.html.
                "token": access_token,

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
        # Blocklist current access token in Redis
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
        # Blacklist refresh token
        # ---------------------------------------------------------------------

        refresh_str = request.data.get("refresh")

        if refresh_str:
            try:
                RefreshToken(refresh_str).blacklist()

            except TokenError:
                # Already invalid or blacklisted.
                # Logout remains idempotent.
                pass

        return Response(
            status=status.HTTP_205_RESET_CONTENT
        )


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
        # No user ID or email is accepted from the client.
        return Response(
            UserSerializer(request.user).data,
            status=status.HTTP_200_OK,
        )