import logging
from django.db import transaction

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.views import TokenRefreshView

from apps.auth_oauth.constants.auth_constants import UserStatus
from apps.auth_oauth.serializers.auth_user_serializer import (
    CustomTokenRefreshSerializer,
)
from apps.auth_oauth.services.strategies.apple import revoke_apple_token
from apps.auth_oauth.utils.auth_user_util import revoke_access_token
from apps.auth_oauth.utils.auth_util import (
    del_jwt_response_cookie,
    set_jwt_response_cookie,
    force_logout_and_clear_tokens,
)
from apps.auth_oauth.utils.user_auth_cache import delete_cached_key
from config.settings import base as settings
from social_django.utils import load_strategy, load_backend
from social_core.actions import do_disconnect
from social_core.exceptions import NotAllowedToDisconnect


logger = logging.getLogger(__name__)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return self.handle_logout(request)

    def post(self, request):
        return self.handle_logout(request)

    def handle_logout(self, request):
        # 1. Get refresh token from cookie
        request.data["refresh"] = request.COOKIES.get(
            settings.SIMPLE_JWT["REFRESH_COOKIE"], None
        )

        refresh_token = request.data["refresh"]

        if not refresh_token:
            return Response({"detail": "Refresh token not found"}, status=400)

        try:
            # 2. Blacklist refresh token
            token = RefreshToken(refresh_token)
            token.blacklist()

            # Remove refresh JTI from Redis
            delete_cached_key(f"refresh_jti:{token['jti']}")

            # 3. Revoke access token using Authorization header
            revoke_access_token(request, settings.SIMPLE_JWT["VERIFYING_KEY"])

            # 4. Clear cookies in response
            resp = Response({"detail": "Logout Successfully"}, status=200)
            del_jwt_response_cookie(resp)
            return resp

        except TokenError as e:
            return Response({"detail": str(e)}, status=400)


class CustomTokenRefreshView(TokenRefreshView):
    """
    Takes a refresh type JSON web token and returns an access type JSON web
    token if the refresh token is valid.

    Args:
        TokenObtainPairView (class): From JWT
    """

    serializer_class = CustomTokenRefreshSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        access = serializer.context["new_access"]
        refresh = serializer.context["new_refresh"]

        response = Response(data)

        # Now safe – response is NOT a dict
        set_jwt_response_cookie(response, access, refresh)

        return response


class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def delete(self, request):
        user = request.user

        # 1 Disconnect Apple (if exists)
        social_user = user.social_auth.filter(provider="apple-id").first()
        if social_user:
            try:
                access_token = social_user.extra_data.get("access_token")
                if access_token:
                    revoke_apple_token(access_token)
                    
                strategy = load_strategy(request)
                backend = load_backend(
                    strategy=strategy,
                    name="apple-id",
                    redirect_uri=None,
                )

                do_disconnect(
                    backend=backend,
                    user=user,
                    association_id=social_user.id,
                )

            except NotAllowedToDisconnect:
                # This is expected when Apple is the only auth method
                logger.info(
                    "Apple is the only auth method for user %s; skipping disconnect",
                    user.id,
                )

            except Exception as e:
                # Unexpected failures (network, Apple outage, etc.)
                logger.warning(
                    "Apple disconnect failed for user %s: %s",
                    user.id,
                    str(e),
                )

        # 2️ Soft-delete user
        user.is_active = False
        user.status = UserStatus.DELETED
        user.save(update_fields=["is_active", "status"])

        # 3️ Logout + revoke local tokens
        response = Response(
            {"detail": "Account deleted successfully."},
            status=status.HTTP_204_NO_CONTENT,
        )
        force_logout_and_clear_tokens(request, response)
        return response
