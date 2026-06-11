import logging
from random import SystemRandom
from urllib.parse import urlencode

import requests
from oauthlib.common import UNICODE_ASCII_CHARACTER_SET
from social_core.backends.oauth import BaseOAuth2
from social_core.exceptions import AuthException, MissingBackend
from social_django.utils import load_strategy, load_backend

from apps.auth_oauth.constants.auth_constants import UserTypes
from apps.auth_oauth.constants.provider_constants import ProviderConstants
from apps.auth_oauth.serializers.social_serializer import SocialSerializer
from apps.auth_oauth.services.factory import OAuthProviderStrategyFactory
from apps.core.exceptions.base_exceptions import BadRequestException
from config.settings.base import (
    SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
    SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
    SOCIAL_AUTH_GOOGLE_OAUTH2_REDIRECT_URI,
    SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_KEY,
    SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_SECRET,
    SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_REDIRECT_URI, )

logger = logging.getLogger(__name__)


class SocialMediaService:

    @staticmethod
    def _generate_state_session_token(length=30, chars=UNICODE_ASCII_CHARACTER_SET):
        rand = SystemRandom()
        state = "".join(rand.choice(chars) for _ in range(length))
        return state

    def validate_provider(self, provider):
        if provider not in [ProviderConstants.GOOGLE, ProviderConstants.LINKEDIN, ProviderConstants.APPLE]:
            raise BadRequestException("Provider name invalid.")

    def get_provider_url(self, provider):
        self.validate_provider(provider)
        if provider == ProviderConstants.GOOGLE:
            return self.get_google_authorization_url()
        elif provider == ProviderConstants.APPLE_ID:
            return self.get_apple_authorization_url()
        else:
            return self.get_linkedin_authorization_url()

    def get_authorization_url(self):
        pass  # we will implement.

    def get_tokens(self, url, form_encoded_payload, *args, **kwargs):

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(
            url, data=form_encoded_payload, headers=headers, timeout=30
        )

        if response.status_code != 200:
            raise BadRequestException(
                f"Failed to get access token {response.json().get('error_description')}."
            )
        json_response = response.json()
        return json_response

    def sign_up_or_login(self, request, *args, **kwargs):
        # Extract data from request
        import traceback
        from urllib.parse import unquote, parse_qs

        try:
            data = request.data

            # Extract state.user_type from request safely
            raw_state = request.data.get("state", "")
            decoded_state = ""

            if raw_state:
                decoded_state = unquote(raw_state) or ""

            logger.info(f"Decoded state: {decoded_state}")

            # Only parse if decoded_state is not empty string
            if decoded_state:
                state_params = parse_qs(decoded_state)
            else:
                state_params = {}

            user_type = (state_params.get("user_type") or [None])[0]

            # Now set user_type in your data or use directly
            data["user_type"] = user_type

            social_serializer = SocialSerializer(data=data)
            social_serializer.is_valid(raise_exception=True)
            validated_data = social_serializer.validated_data
            authorization_code = validated_data.get("code")
            provider = validated_data.get("provider")
            authorization_code_grant_type = "authorization_code"

        except Exception as e:
            tb = traceback.format_exc()  # full traceback
            raise BadRequestException(
                f"Get data from request error: {e.args}\nTraceback:\n{tb}"
            )

        try:
            logger.info(
                f"Print: SocialMediaService.get_tokens_for_user provider:{provider} and user_type: {user_type}"
            )
            token = None
            self.validate_provider(provider)

            try:
                if provider == ProviderConstants.GOOGLE:
                    provider = ProviderConstants.GOOGLE_OAUTH2
                    url = "https://oauth2.googleapis.com/token"
                    payload_dict = {
                        "grant_type": authorization_code_grant_type,
                        "code": authorization_code,
                        "redirect_uri": SOCIAL_AUTH_GOOGLE_OAUTH2_REDIRECT_URI,
                        "client_id": SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
                        "client_secret": SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
                    }
                    form_encoded_payload = urlencode(payload_dict)
                    token_response = self.get_tokens(url, form_encoded_payload)
                    token = token_response.get("access_token", None)
                else:
                    provider = ProviderConstants.LINKEDIN_OPENIDCONNECT
                    url = "https://www.linkedin.com/oauth/v2/accessToken"
                    payload_dict = {
                        "grant_type": authorization_code_grant_type,
                        "code": authorization_code,
                        "redirect_uri": SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_REDIRECT_URI,
                        "client_id": SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_KEY,
                        "client_secret": SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_SECRET,
                    }
                    form_encoded_payload = urlencode(payload_dict)
                    token_response = self.get_tokens(url, form_encoded_payload)
                    token = token_response.get("access_token", None)
                if not token:
                    raise BadRequestException("Access token is required.")
                return self.convert_token(request, provider, token, user_type)

            except BadRequestException as e:
                raise
            except Exception as e:
                raise BadRequestException(
                    f"Error in getting access token second line {e}"
                )
        except BadRequestException as e:
            raise
        except Exception as e:
            raise BadRequestException(
                f"Error in getting access token first line {e.args}"
            )

    def convert_token(self, request, provider, token, user_type=None, is_mobile=None):
        strategy = load_strategy(request)
        if not strategy:
            raise BadRequestException("Could not load strategy.")
        try:
            backend_instance: BaseOAuth2 = load_backend(
                strategy, provider, redirect_uri=None
            )
        except MissingBackend:
            raise BadRequestException(
                f"Provider '{provider}' not found or not configured."
            )
        except Exception as e:
            raise BadRequestException(f"Error loading backend: {str(e)}")

        try:
            # Set user_type in user
            # request.user.user_type = user_type
            user_type_raw = (
                user_type
                if user_type
                else request.data.get("state", UserTypes.APPLICANT.value)
            )
            allowed_types = {UserTypes.APPLICANT.value, UserTypes.RECRUITER.value}
            if user_type_raw not in allowed_types:
                raise BadRequestException(
                    "Authentication failed. User could not be authenticated or created."
                )
            user_type = (
                UserTypes.ADMIN_RECRUITER.value
                if user_type_raw == UserTypes.RECRUITER.value
                else user_type_raw
            )

            request.session["user_type"] = user_type
            if provider.lower() == ProviderConstants.APPLE_ID.lower():
                # token is dict from AppleOAuthStrategy.verify_token()
                token_for_backend = token.get("id_token")
                # optionally store email in request for profile creation
                request.data["apple_email"] = token.get("email")
                request.data["apple_first_name"] = token.get("first_name")
                request.data["apple_last_name"] = token.get("last_name")
            else:
                token_for_backend = token  # usual string for LinkedIn/Google
            user = backend_instance.do_auth(
                access_token=token_for_backend,
                user=request.user if request.user.is_authenticated else None,
            )
        except AuthException as e:
            raise BadRequestException(f"Authentication failed {str(e)}.")
        except Exception as e:
            logger.error(
                f"Unexpected error during social authentication: {e}", exc_info=True
            )
            raise BadRequestException(str(e))

        if user:
            if not user.is_active:
                raise BadRequestException("This user account has been disabled.")

            # Generate JWT tokens
            # tokens = self.get_tokens_for_user(user)
            from apps.auth_oauth.utils.token import issue_token_to_user
            from apps.auth_oauth.services.user_company_profile_service import (
                UserCompanyProfileService,
            )

            if is_mobile:
                user_profile_applicant = UserCompanyProfileService().get_by_userid(
                    user.pk, user_type
                )
                if not user_profile_applicant:
                    raise BadRequestException("Mobile only support applicant.")
                request.data["user_company_profile_id"] = (
                    user_profile_applicant.pk if user_profile_applicant else None
                )
            return issue_token_to_user(request=request, user=user)
        else:
            raise BadRequestException(
                "Authentication failed. User could not be authenticated or created."
            )

    @staticmethod
    def get_provider_auth_url(provider_name):
        """
        Get the redirect URL for the given provider
        :param provider_name: name of the provider
        :return: html form
        """
        return OAuthProviderStrategyFactory.get_redirect_url(provider_name)
