from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from apps.auth_oauth.constants.auth_constants import ProfileStatus


class CustomJWTAuthentication(JWTAuthentication):
    """
    Override JWTAuthentication to:
    - Decode RS256 tokens manually
    - Enforce Redis-based JTI verification
    """

    def get_validated_token(self, raw_token):
        """
        Override SimpleJWT's token validation.
        We still call super() so SimpleJWT can run its built-in checks.
        """
        from apps.auth_oauth.utils.utils import jwt_decode_rs256_token
        from django.core.cache import cache as redis_client

        # 1) Let SimpleJWT do standard validation (expiry, signature, etc.)
        validated_token = super().get_validated_token(raw_token)

        # 2) Decode RS256 token manually (your function)
        try:
            payload = jwt_decode_rs256_token(
                token=raw_token,
                public_key=settings.SIMPLE_JWT["VERIFYING_KEY"],
            )
        except Exception as e:
            raise InvalidToken()

        # 3) Extract & verify JTI
        jti = payload.get("jti")
        if not jti:
            raise InvalidToken()

        # 4) Get cached value and normalize bytes -> str
        cached_value = redis_client.get(f"access_jti:{jti}")
        if isinstance(cached_value, bytes):
            cached_value = cached_value.decode("utf-8")

        if cached_value != "active":
            raise InvalidToken()

        return validated_token

    def get_user(self, validated_token):
        """
        Safely validates user vitality and active profile states.
        Bypasses super().get_user() internal deactivation crash to return a clean 401.
        """
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # 1. Fetch the user manually using the user_id stored in the token payload
        try:
            user_id = validated_token[
                settings.SIMPLE_JWT.get("USER_ID_CLAIM", "user_id")
            ]
            user = User.objects.get(**{User._meta.pk.name: user_id})
        except (User.DoesNotExist, KeyError):
            raise InvalidToken(
                detail=_("User account not found."), code="user_not_found"
            )

        # 2. Handle account deactivation and deletion explicitly
        if user.status == ProfileStatus.DELETED:
            raise InvalidToken(
                {"detail": _("Your account has been deleted."), "code": "user_deleted"}
            )

        if not user.is_active:
            raise InvalidToken(
                {
                    "detail": _(
                        "Your account has been deactivated. Please contact support."
                    ),
                    "code": "user_deactivated",
                }
            )

        return user
