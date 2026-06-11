from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from apps.auth_oauth.services.strategies.base import OAuthProviderStrategy
from apps.core.exceptions.base_exceptions import BadRequestException
from config.settings.base import SOCIAL_AUTH_GOOGLE_OAUTH2_KEY, SOCIAL_AUTH_GOOGLE_OAUTH2_REDIRECT_URI


class GoogleAuthStrategy(OAuthProviderStrategy):

    def __init__(self, client_id: str):
        self.client_id = client_id

    def verify_token(self, id_token_value: str, token: str, code: str | None = None) -> str:
        try:
            id_info = id_token.verify_oauth2_token(
                id_token_value, google_requests.Request(), self.client_id
            )
            if not id_info.get("sub"):
                raise BadRequestException("fail to verify.")
        except Exception as e:
            raise BadRequestException(e)
        return token

    @staticmethod
    def get_redirect_url():
        return (
                "https://accounts.google.com/o/oauth2/auth?response_type=code&"
                + f"client_id={SOCIAL_AUTH_GOOGLE_OAUTH2_KEY}&redirect_uri={SOCIAL_AUTH_GOOGLE_OAUTH2_REDIRECT_URI}"
                + "&scope=profile email&access_type=offline"
        )
