from urllib.parse import urlencode

from config.settings.base import (
    MOBILE_SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_KEY,
    MOBILE_SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_REDIRECT_URI,
    MOBILE_SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_SECRET, SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_KEY,
    SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_REDIRECT_URI,
)
from .base import OAuthProviderStrategy

"""
LinkedIn does not use ID tokens like google and apple. Instead, it uses an access token to get user info.
"""


class LinkedInOAuthStrategy(OAuthProviderStrategy):

    def __init__(self, client_id: str = ""):
        pass  # ignore client_id

    def verify_token(self, id_token_value: str, token: str, code: str | None = None) -> str:
        url = "https://www.linkedin.com/oauth/v2/accessToken"
        payload_dict = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": MOBILE_SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_REDIRECT_URI,
            "client_id": MOBILE_SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_KEY,
            "client_secret": MOBILE_SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_SECRET,
        }
        form_encoded_payload = urlencode(payload_dict)
        from apps.auth_oauth.services.social_media_service import SocialMediaService
        token_response = SocialMediaService().get_tokens(url, form_encoded_payload)
        return token_response.get("access_token", None)

    @staticmethod
    def get_redirect_url():
        return (
                "https://www.linkedin.com/oauth/v2/authorization?response_type=code&"
                + f"client_id={SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_KEY}&redirect_uri={SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_REDIRECT_URI}"
                + "&scope=openid%20email%20profile"
        )
