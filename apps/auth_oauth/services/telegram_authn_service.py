import base64
import logging
import uuid

import requests
from django.conf import settings
from django.core.cache import cache
from jose import jwt as jose_jwt, JWTError

from apps.auth_oauth.constants.auth_constants import (
    ProfileStatus,
    UserStatus,
    UserState,
    UserTypes,
)
from apps.auth_oauth.constants.provider_constants import ProviderConstants
from apps.base.utils.base_util import get_default_company

logger = logging.getLogger(__name__)

JWKS_CACHE_KEY = "telegram:jwks"
JWKS_CACHE_TTL = 600


def _get_telegram_jwks() -> dict:
    """Fetch and cache Telegram JWKS for 10 minutes (same pattern as WSO2)."""
    jwks = cache.get(JWKS_CACHE_KEY)
    if jwks is not None:
        return jwks

    resp = requests.get(settings.TELEGRAM_JWKS_URI, timeout=5)
    resp.raise_for_status()
    jwks = resp.json()

    cache.set(JWKS_CACHE_KEY, jwks, timeout=JWKS_CACHE_TTL)
    return jwks


class TelegramAuthNError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Telegram OIDC error {status_code}: {detail}")


class TelegramAuthNService:

    @staticmethod
    def build_telegram_auth_url(state: str, code_challenge: str) -> str:
        """
        Build the Telegram OAuth authorization URL.
        Always uses TELEGRAM_REDIRECT_URI from settings — the server's
        registered redirect URI — so the token exchange can use the same value.
        """
        from urllib.parse import urlencode

        params = {
            "client_id": settings.TELEGRAM_CLIENT_ID,
            "redirect_uri": settings.TELEGRAM_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid profile phone",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"https://oauth.telegram.org/auth?{urlencode(params)}"

    @staticmethod
    def exchange_code(code: str, code_verifier: str, redirect_uri: str) -> dict:
        """
        Exchange authorization code + PKCE verifier for Telegram token response.
        Returns the raw token response dict;
        """
        credentials = base64.b64encode(
            f"{settings.TELEGRAM_CLIENT_ID}:{settings.TELEGRAM_CLIENT_SECRET}".encode()
        ).decode()

        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": settings.TELEGRAM_CLIENT_ID,
            "code_verifier": code_verifier,
        }
        try:
            resp = requests.post(
                settings.TELEGRAM_TOKEN_URI,
                data=payload,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {credentials}",
                },
                timeout=10,
            )

        except requests.RequestException as exc:
            raise TelegramAuthNError(502, f"Telegram token endpoint unreachable: {exc}")

        if not resp.ok:
            try:
                body = resp.json()
                detail = body.get("error_description") or body.get("error") or resp.text
            except Exception:
                detail = resp.text
            raise TelegramAuthNError(resp.status_code, detail)

        try:
            token_response = resp.json()
        except Exception:
            raise TelegramAuthNError(
                502, f"Telegram returned non-JSON response: {resp.text[:200]}"
            )
        logger.warning("Telegram token response keys: %s", list(token_response.keys()))
        if not token_response.get("id_token"):
            raise TelegramAuthNError(502, "Telegram did not return id_token.")
        return token_response

    @staticmethod
    def verify_id_token(id_token: str) -> dict:
        """
        Verify Telegram id_token signature and claims against Telegram's JWKS.
        Returns decoded payload.
        """
        try:
            jwks = _get_telegram_jwks()
            payload = jose_jwt.decode(
                id_token,
                jwks,
                algorithms=["RS256"],
                audience=settings.TELEGRAM_CLIENT_ID,
                issuer="https://oauth.telegram.org",
                options={"verify_exp": True},
            )
            return payload
        except JWTError as exc:
            raise TelegramAuthNError(401, f"Invalid Telegram id_token: {exc}")
        except Exception as exc:
            raise TelegramAuthNError(502, f"Telegram JWKS error: {exc}")

    @staticmethod
    def get_or_create_user(claims: dict):
        """
        Get-or-create Django User + applicant UserCompanyProfile from verified id_token claims.
        Telegram login is applicant-only; this method always produces an applicant profile.
        """
        from apps.auth_oauth.models.auth_models import User
        from apps.auth_oauth.services.user_company_profile_service import (
            UserCompanyProfileService,
        )

        telegram_sub = str(claims["sub"])

        full_name = (claims.get("name") or "").strip()
        name_parts = full_name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # email = f"{telegram_sub}@telegram.placeholder"
        picture = claims.get("picture") or ""
        phone_number = claims.get("phone_number") or ""

        user = User.objects.filter(
            telegram_chat_id=telegram_sub, status=UserStatus.ACTIVE, is_active=True
        ).first()

        if not user:
            tg_username = claims.get("preferred_username") or f"tg_{telegram_sub}"
            if User.objects.filter(username=tg_username).exists():
                tg_username = f"tg_{telegram_sub}_{uuid.uuid4().hex[:6]}"

            user = User(
                telegram_chat_id=telegram_sub,
                email=None,
                username=phone_number,
                first_name=first_name,
                last_name=last_name,
                login_type="social",
                status=UserStatus.ACTIVE,
                state=UserState.COMPLETE_VERIFY_OPT,
                is_active=True,
                is_login=True,
            )
            user.set_unusable_password()
            user.save()

        applicant_profile = UserCompanyProfileService.get_by_userid(
            user.pk, UserTypes.APPLICANT.value
        )
        if not applicant_profile:
            default_company = get_default_company()
            social_data = {
                "user": user,
                "status": ProfileStatus.ACTIVE,
                "type": UserTypes.APPLICANT.value,
                "provider": ProviderConstants.TELEGRAM,
                "image_url": picture,
                "company": default_company.pk if default_company else None,
            }
            applicant_profile = UserCompanyProfileService.social_create(social_data)
            if applicant_profile.profile and phone_number:
                applicant_profile.profile.phone_number = phone_number
                applicant_profile.profile.save(update_fields=["phone_number"])

        if not user.default_user_profile_company:
            user.default_user_profile_company = applicant_profile.pk
            user.save(update_fields=["default_user_profile_company"])

        return user
