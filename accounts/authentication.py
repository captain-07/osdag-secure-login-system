from django.core.cache import cache
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed


class BlocklistAwareJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        # First let simplejwt do its normal signature/expiry check.
        validated_token = super().get_validated_token(raw_token)

        jti = validated_token.get("jti")
        # If this jti was written to Redis at logout time, the token is
        # cryptographically valid but explicitly revoked — reject it.
        if cache.get(f"blocklist:{jti}"):
            raise AuthenticationFailed("Token has been revoked.")

        return validated_token