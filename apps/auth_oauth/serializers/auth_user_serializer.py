from django.conf import settings
from rest_framework import serializers
from rest_framework_simplejwt.serializers import (
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.tokens import UntypedToken, RefreshToken

from apps.auth_oauth.utils.auth_user_util import revoke_access_token
from apps.auth_oauth.utils.auth_util import set_jwt_response_cookie
from apps.auth_oauth.utils.user_auth_cache import delete_cached_key, set_cached_value


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    refresh = serializers.CharField(required=False)

    def validate(self, attrs):

        request = self.context["request"]

        refresh_token = attrs.get("refresh") or request.COOKIES.get(
            settings.SIMPLE_JWT["REFRESH_COOKIE"]
        )

        if not refresh_token:
            raise serializers.ValidationError("Refresh token missing.")

        attrs["refresh"] = refresh_token

        old_refresh_token_str = attrs["refresh"]

        try:
            old_refresh = RefreshToken(old_refresh_token_str)
            old_jti = str(old_refresh["jti"])
        except Exception as e:
            raise serializers.ValidationError("Invalid refresh token.") from e

        try:
            delete_cached_key(f"refresh_jti:{old_jti}")
        except Exception as e:
            raise serializers.ValidationError(
                "Could not delete old refresh jti from Redis"
            ) from e

        # Check in case if user call refresh with access token header
        request = self.context.get("request")

        try:
            revoke_access_token(request, settings.SIMPLE_JWT["VERIFYING_KEY"])
        except Exception as e:
            raise serializers.ValidationError(
                "Could not revoke old access token."
            ) from e

        # Call built-in validate() — this generates new access (and possibly refresh) tokens
        try:
            data = super().validate(attrs)
        except Exception as e:
            raise serializers.ValidationError("Token refresh failed.") from e

        # Get the new access token string
        access_token_str = data["access"]

        try:
            token = UntypedToken(access_token_str)  # works for access/refresh
        except Exception:
            raise serializers.ValidationError("Invalid token generated.")

        jti = token.get("jti")
        exp = token.get("exp")

        # Store JTI in Redis with TTL equal to token expiry
        # e.g., key: access_jti:{jti} -> value: user_id or "active"
        redis_key = f"access_jti:{jti}"

        # Convert token.current_time (datetime) to timestamp
        current_timestamp = int(token.current_time.timestamp())
        ttl_seconds = exp - current_timestamp  # seconds until expiration

        try:
            set_cached_value(redis_key, "active", ttl_seconds)
        except Exception as e:
            raise serializers.ValidationError(
                "Could not store access token in Redis."
            ) from e

        refresh_token_str = data.get("refresh")
        if refresh_token_str:
            try:
                refresh_token = UntypedToken(refresh_token_str)
                refresh_jti = refresh_token.get("jti")
                refresh_exp = refresh_token.get("exp")
                refresh_ttl = max(refresh_exp - current_timestamp, 0)
                set_cached_value(f"refresh_jti:{refresh_jti}", "active", refresh_ttl)
            except Exception as e:
                raise serializers.ValidationError(
                    "Could not store refresh token in Redis."
                ) from e

            # Store tokens for the view to use
            self.context["new_access"] = data.get("access")
            self.context["new_refresh"] = data.get("refresh")

        return data
