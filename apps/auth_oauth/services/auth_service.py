import logging

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

from apps.auth_oauth.constants.auth_constants import UserTypes
from apps.auth_oauth.constants.provider_constants import ProviderConstants
from apps.auth_oauth.services.factory import OAuthProviderStrategyFactory
from apps.auth_oauth.services.social_media_service import SocialMediaService
from apps.auth_setting.setting import settings
from apps.base.constants.base_constants import UserAgentType
from config.settings.base import (
    MOBILE_SOCIAL_AUTH_GOOGLE_OAUTH2_KEY_IOS,
    MOBILE_SOCIAL_AUTH_GOOGLE_OAUTH2_KEY_ANDROID,
)

logger = logging.getLogger(__name__)


def mask_token(token: str, visible: int = 4) -> str:
    """Return a token with only the last `visible` characters shown."""
    if not token or not isinstance(token, str):
        return ""
    return f"{'*' * (len(token) - visible)}{token[-visible:]}"


class SocialAuthService:
    @staticmethod
    def authenticate(request, *args, **kwargs):
        """
        Authenticate a user via a social provider, verify token, and return JWT tokens.

        Logs:
            - Includes request correlation ID (if provided via request.META['X-Request-ID'] or generated).
            - Masks tokens for safe logging.
        """
        request_id = request.META.get("HTTP_X_REQUEST_ID", None) or kwargs.get("request_id", "no-request-id")
        logger.info("[request_id=%s] Starting social authentication process.", request_id)

        try:
            # 1. Extract request data
            provider = request.data.get("provider")
            token = request.data.get("token")
            id_token = request.data.get("id_token")
            code = request.data.get("code")
            user_type = request.data.get("user_type", UserTypes.APPLICANT.value)

            logger.debug(
                "[request_id=%s] Authentication request: provider=%s, user_type=%s, token=%s, id_token=%s, code=%s",
                request_id,
                provider,
                user_type,
                mask_token(token),
                mask_token(id_token),
                mask_token(code),
            )

            if not provider:
                return {"error": "Provider is required."}, status.HTTP_400_BAD_REQUEST

            # 2. Get client ID
            client_id = SocialAuthService().get_client_id(request, provider)
            logger.debug("[request_id=%s] Resolved client_id=%s", request_id, client_id)

            # 3. Verify provider token
            access_token = OAuthProviderStrategyFactory.verify_token(
                client_id=client_id,
                provider_name=provider,
                id_token_value=id_token,
                token=token,
                code=code
            )
            logger.debug("[request_id=%s] Access token verified successfully for provider=%s", request_id, provider)

            # 4. Build user and JWT tokens
            provider_name = SocialAuthService().get_provider_name(provider)
            response = SocialMediaService().convert_token(
                request, provider_name, access_token, user_type, True
            )

            logger.info(
                "[request_id=%s] Social authentication successful for provider=%s, user_type=%s",
                request_id,
                provider,
                user_type,
            )

            return response.data, response.status_code

        except (APIException, ValidationError) as e:
            logger.warning(
                "[request_id=%s] Authentication rejected: %s",
                request_id,
                str(e),
            )
            raise
        except Exception as e:
            logger.exception(
                "[request_id=%s] Social authentication failed for provider=%s, user_type=%s: %s",
                request_id,
                request.data.get("provider"),
                request.data.get("user_type", UserTypes.APPLICANT.value),
                str(e),
            )
            return {"error": "Authentication failed.", "details": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR

    @staticmethod
    def get_provider_name(provider):
        SocialMediaService().validate_provider(provider)
        if provider == ProviderConstants.LINKEDIN:
            return ProviderConstants.LINKEDIN_OPENIDCONNECT
        if provider == ProviderConstants.APPLE:
            return ProviderConstants.APPLE_ID
        return ProviderConstants.GOOGLE_OAUTH2

    @staticmethod
    def get_client_id(request, provider=None):
        user_agent = request.user_agent
        if not user_agent or not getattr(user_agent, "is_mobile", False):
            return None
        os_family = (getattr(user_agent.os, "family", "") or "").lower()
        if provider == ProviderConstants.APPLE:
            if UserAgentType.IOS in os_family:
                return getattr(settings, "SOCIAL_AUTH_APPLE_BUNDLE_ID", None)
            return getattr(settings, "SOCIAL_AUTH_APPLE_ID_CLIENT", None)
        if UserAgentType.ANDROID in os_family:
            return MOBILE_SOCIAL_AUTH_GOOGLE_OAUTH2_KEY_ANDROID
        if UserAgentType.IOS in os_family:
            return MOBILE_SOCIAL_AUTH_GOOGLE_OAUTH2_KEY_IOS
        return None
