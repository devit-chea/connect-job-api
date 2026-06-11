import requests
from jwt.algorithms import RSAAlgorithm

from apps.core.exceptions.base_exceptions import BadRequestException
from config.settings.base import SOCIAL_AUTH_APPLE_KEY_ID, SOCIAL_AUTH_APPLE_TEAM_ID,  \
    SOCIAL_AUTH_APPLE_PRIVATE_KEY, SOCIAL_AUTH_APPLE_ID_REDIRECT_URI, SOCIAL_AUTH_APPLE_BUNDLE_ID
from .base import OAuthProviderStrategy
import jwt
import time


APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"
APPLE_TOKEN_URL = "https://appleid.apple.com/auth/token"

def generate_apple_client_secret():
    headers = {
        "kid": SOCIAL_AUTH_APPLE_KEY_ID,
    }
    payload = {
        "iss": SOCIAL_AUTH_APPLE_TEAM_ID,
        "iat": int(time.time()),
        "exp": int(time.time()) + 15777000,
        "aud": "https://appleid.apple.com",
        "sub": SOCIAL_AUTH_APPLE_BUNDLE_ID,
    }
    client_secret = jwt.encode(
        payload,
        SOCIAL_AUTH_APPLE_PRIVATE_KEY,
        algorithm="ES256",
        headers=headers
    )
    return client_secret

def apple_exchange_code(authorization_code: str):
    client_secret = generate_apple_client_secret()

    payload = {
        "client_id": SOCIAL_AUTH_APPLE_BUNDLE_ID,
        "client_secret": client_secret,
        "code": authorization_code,
        "grant_type": "authorization_code",
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    res = requests.post(APPLE_TOKEN_URL, data=payload, headers=headers)
    data = res.json()

    if "id_token" not in data:
        raise BadRequestException(f"Could not exchange code: {data}")

    return data  # contains id_token, access_token (useless), etc.

def revoke_apple_token(token):
    import requests

    client_secret = generate_apple_client_secret()

    payload = {
        "client_id": SOCIAL_AUTH_APPLE_BUNDLE_ID,
        "client_secret": client_secret,
        "token": token,
        "token_type_hint": "access_token",
    }
    headers = {"content-type": "application/x-www-form-urlencoded"}
    requests.post(
        "https://appleid.apple.com/auth/revoke", data=payload, headers=headers
    )


class AppleOAuthStrategy(OAuthProviderStrategy):
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.access_token_for_social_service = None

    @staticmethod
    def get_apple_public_key(kid: str):
        response = requests.get(APPLE_KEYS_URL, timeout=5)
        keys = response.json().get("keys", [])
        for key in keys:
            if key["kid"] == kid:
                return RSAAlgorithm.from_jwk(key)
        raise ValueError("Unable to find matching Apple public key.")

    def verify_token(self, id_token_value: str, token: str, code: str | None = None) -> dict:

        if code and not id_token_value:
            data = apple_exchange_code(code)
            id_token_value = data["id_token"]
        unverified_header = jwt.get_unverified_header(id_token_value)
        public_key = self.get_apple_public_key(unverified_header["kid"])
        try:
            decoded = jwt.decode(
                id_token_value,
                public_key,
                algorithms=["RS256"],
                audience=SOCIAL_AUTH_APPLE_BUNDLE_ID,
                issuer="https://appleid.apple.com"
            )
            return {
                "email": decoded.get("email"),
                "name": " ",
                "provider_id": decoded.get("sub"),
                "id_token": id_token_value,
                "email_verified": decoded.get("email_verified"),
                "raw_claims": decoded,
            }
        except jwt.ExpiredSignatureError:
            raise ValueError("Apple ID token has expired.")
        except jwt.InvalidAudienceError:
            raise ValueError("Apple ID token has invalid audience.")
        except jwt.InvalidIssuerError:
            raise ValueError("Apple ID token has invalid issuer.")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid Apple ID token: {str(e)}")

    @staticmethod
    def get_redirect_url():
        return ""
