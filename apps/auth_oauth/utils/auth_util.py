from datetime import datetime, timedelta
from urllib.parse import unquote, parse_qs

from django.shortcuts import redirect
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from social_core.backends.google import GoogleOAuth2
from social_core.backends.linkedin import LinkedinOpenIdConnect

from apps.auth_oauth.constants.auth_constants import (
    ProfileStatus,
    UserState,
    UserTypes,
)
from apps.auth_oauth.models.user_authentication_session_model import (
    UserAuthenticationSession,
)
from apps.auth_oauth.serializers.jwt_serializer import WDGTokenObtainPairSerializer
from apps.auth_oauth.utils.auth_user_util import revoke_access_token
from apps.auth_oauth.utils.user_auth_cache import delete_cached_key
from apps.auth_oauth.utils.user_auth_cache import set_cached_value
from apps.auth_oauth.utils.utils import jwt_decode_rs256_token
from apps.base.utils.base_util import get_client_ip
from config.settings import base as settings


def set_jwt_refresh_cookie(response, refresh_token):
    refresh_expiration = timezone.now() + settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
    refresh_cookie_name = settings.SIMPLE_JWT["REFRESH_COOKIE"]
    refresh_cookie_path = settings.SIMPLE_JWT["REFRESH_COOKIE_PATH"]
    cookie_secure = settings.SIMPLE_JWT["COOKIE_SECURE"]
    cookie_httponly = settings.SIMPLE_JWT["COOKIE_HTTP_ONLY"]
    cookie_samesite = settings.SIMPLE_JWT["COOKIE_SAMESITE"]
    cookie_domain = settings.SIMPLE_JWT["COOKIE_DOMAIN"]

    if refresh_cookie_name:
        response.set_cookie(
            refresh_cookie_name,
            refresh_token,
            expires=refresh_expiration,
            secure=cookie_secure,
            httponly=cookie_httponly,
            samesite=cookie_samesite,
            path=refresh_cookie_path,
            domain=cookie_domain,
        )


def unset_jwt_cookies(response):
    refresh_cookie_name = settings.SIMPLE_JWT["REFRESH_COOKIE"]
    refresh_cookie_path = settings.SIMPLE_JWT["REFRESH_COOKIE_PATH"]
    cookie_samesite = settings.SIMPLE_JWT["COOKIE_SAMESITE"]
    cookie_domain = settings.SIMPLE_JWT["COOKIE_DOMAIN"]
    if refresh_cookie_name:
        response.delete_cookie(
            refresh_cookie_name,
            path=refresh_cookie_path,
            samesite=cookie_samesite,
            domain=cookie_domain,
        )


def set_jwt_response_cookie(response, access_token, refresh_token):
    access_life_time = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]
    response.set_cookie(
        key=settings.SIMPLE_JWT["ACCESS_COOKIE"],
        value=str(access_token),
        expires=datetime.now() + access_life_time,
        secure=settings.SIMPLE_JWT["COOKIE_SECURE"],
        httponly=settings.SIMPLE_JWT["COOKIE_HTTP_ONLY"],
        samesite=settings.SIMPLE_JWT["COOKIE_SAMESITE"],
        domain=settings.SIMPLE_JWT["COOKIE_DOMAIN"],
    )

    refresh_life_time = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
    response.set_cookie(
        key=settings.SIMPLE_JWT["REFRESH_COOKIE"],
        value=str(refresh_token),
        expires=datetime.now() + refresh_life_time,
        secure=settings.SIMPLE_JWT["COOKIE_SECURE"],
        httponly=settings.SIMPLE_JWT["COOKIE_HTTP_ONLY"],
        samesite=settings.SIMPLE_JWT["COOKIE_SAMESITE"],
        domain=settings.SIMPLE_JWT["COOKIE_DOMAIN"],
    )


def set_tenant_domain_response_cookie(response, tenant_domain: None):
    response.set_cookie(
        key="tenant_domain",
        value=tenant_domain,
        expires=datetime.now() + timedelta(days=365),
        secure=False,
        httponly=False,
        samesite=settings.SIMPLE_JWT["COOKIE_SAMESITE"],
        domain=settings.SIMPLE_JWT["COOKIE_DOMAIN"],
    )


def del_jwt_response_cookie(
    response,
    is_remove_access=True,
    is_remove_refresh=True,
    is_remove_tenant_domain=True,
):
    if is_remove_access:
        response.delete_cookie(
            key=settings.SIMPLE_JWT["ACCESS_COOKIE"],
            domain=settings.SIMPLE_JWT["COOKIE_DOMAIN"],
            samesite=settings.SIMPLE_JWT["COOKIE_SAMESITE"],
        )
    if is_remove_refresh:
        response.delete_cookie(
            key=settings.SIMPLE_JWT["REFRESH_COOKIE"],
            domain=settings.SIMPLE_JWT["COOKIE_DOMAIN"],
            samesite=settings.SIMPLE_JWT["COOKIE_SAMESITE"],
        )
    if is_remove_tenant_domain:
        response.delete_cookie(key="tenant_domain")


def is_jwt_token_expired(token):
    public_key = settings.SIMPLE_JWT["VERIFYING_KEY"]
    decoded_token = jwt_decode_rs256_token(token, public_key)
    if not decoded_token:
        return True

    # Extract expiration time ('exp') from the token
    exp_timestamp = decoded_token.get("exp")
    if exp_timestamp:
        expiration_time = datetime.fromtimestamp(exp_timestamp)
        if expiration_time < datetime.now():
            return True

    return False


def get_is_user_logged_in(data):
    user_auth_session = UserAuthenticationSession.objects.filter(**data)
    is_user_logged_in = user_auth_session.exists()
    user_auth_session_instance = user_auth_session.last()
    return is_user_logged_in, user_auth_session_instance

def get_remark(user_agent):
    if user_agent.is_bot:
        return "bot"
    elif user_agent.is_email_client:
        return "email_client"
    elif user_agent.is_mobile:
        return "mobile"
    elif user_agent.is_pc:
        return "pc"
    elif user_agent.is_tablet:
        return "tablet"
    elif user_agent.is_touch_capable:
        return "touch_capable"
    else:
        return "other"


def get_user_agent_info(user_instance, request, user_company_profile_id=None):
    user_agent = request.user_agent

    def safe_get(attr, key):
        return getattr(attr, key, None) if attr else None

    data = {
        "ip_address": get_client_ip(request),
        "device": safe_get(user_agent.device, "family"),
        "device_branch": safe_get(user_agent.device, "brand"),
        "device_model": safe_get(user_agent.device, "model"),
        "browser": safe_get(user_agent.browser, "family"),
        "browser_version": safe_get(user_agent.browser, "version_string"),
        "os": safe_get(user_agent.os, "family"),
        "os_version": safe_get(user_agent.os, "version_string"),
        "remark": get_remark(user_agent),
        "user_id": user_instance.pk if user_instance else None,
    }
    # Todo: will remove soon, _type = request.data.get("state", None) or ""
    
    # Check if request.data is a non-empty list
    if isinstance(request.data, list) and request.data:
        # Get the first dictionary in the list
        data_dict = request.data[0]
        _type = data_dict.get("state", None) or ""
    else:
        # Fallback for when it's a regular dict or empty/malformed list
        _type = request.data.get("state", None) or ""
        
    data["type"] = _type
    if _type:
        # noted :
        user_company_profile_instance = user_instance.user_company_profile_user.filter(
            type=_type,
            user=user_instance,
            company__isnull=True,
            profile__isnull=True,
            provider__in=[GoogleOAuth2.name, LinkedinOpenIdConnect.name],
        ).first()
        user_company_profile_id = (
            user_company_profile_instance.id if user_company_profile_instance else None
        )
    is_user_logged_in, user_auth_session_instance = get_is_user_logged_in(data)
    if not user_company_profile_id:
        user_company_profile_id = (
            user_auth_session_instance.user_company_profile_id
            if is_user_logged_in and user_auth_session_instance
            else user_instance.default_user_profile_company or None
        )
    data["user_company_profile_id"] = user_company_profile_id

    return data


def generate_session(user_agent_info, user_company_profile_id, refresh, user_instance):
    user_authentication_session = UserAuthenticationSession.objects.create(
        **user_agent_info
    )
    user_company_profile_instance = user_instance.user_company_profile_user.filter(
        id=user_company_profile_id
    ).first()
    if user_company_profile_instance:
        refresh["profile_id"] = user_company_profile_instance.profile_id
        refresh["company_id"] = user_company_profile_instance.company_id
        refresh["user_company_profile_id"] = user_company_profile_id
        refresh["user_authentication_session_id"] = user_authentication_session.pk
        refresh["type"] = user_company_profile_instance.type

        refresh["company_status"] = getattr(user_company_profile_instance.company, "status", None)
        refresh["user_company_profile_state"] = getattr(user_company_profile_instance, "state", None)
        refresh["profile_status"] = getattr(user_company_profile_instance.profile, "status", None)
    user_instance.default_user_profile_company = user_company_profile_id
    user_instance.is_login = True
    user_instance.save()

def generate_jwt_token(user_instance, request, user_company_profile_id=None):
    refresh = WDGTokenObtainPairSerializer.get_token(user_instance)
    user_agent_info = get_user_agent_info(
        user_instance, request, user_company_profile_id
    )
    user_company_profile_id = (
        user_company_profile_id
        if user_company_profile_id
        else user_agent_info.get("user_company_profile_id")
    )
    
    get_is_setup_profile(user_instance, user_company_profile_id)
    generate_session(user_agent_info, user_company_profile_id, refresh, user_instance)
    
    # Cache jti
    access_token = refresh.access_token
    access_token_jti = str(access_token["jti"])
    refresh_jti = str(refresh["jti"])
    try:
        # Store access token JTI
        set_cached_value(
            key=f"access_jti:{access_token_jti}",
            value="active",
            timeout=int(access_token.lifetime.total_seconds()),
        )
        # Store refresh token JTI
        set_cached_value(
            key=f"refresh_jti:{refresh_jti}",
            value="active",
            timeout=int(refresh.lifetime.total_seconds()),
        )
    except Exception as e:
        raise TimeoutError("Could not connect to Redis or store key") from e
    
    refresh_token = str(refresh)
    access_token = str(access_token)
    
    return access_token, refresh_token


def redirect_to_frontend(request, response):
    access_token = response.data.get(settings.SIMPLE_JWT["ACCESS_COOKIE"])
    refresh_token = response.data.get(settings.SIMPLE_JWT["REFRESH_COOKIE"])
    web_url = settings.WEB_BASE_URL
    response = redirect(f"{web_url}")
    set_jwt_response_cookie(response, access_token, refresh_token)
    return response


def get_is_setup_profile(user, user_company_profile_id):
    current_profile = user.user_company_profile_user.filter(
        id=user_company_profile_id
    ).first()
    profile_type = current_profile.type if current_profile else None
    is_setup_profile = user.profile_user.filter(
        user=user, profile_type=profile_type, status__isnull=False
    ).exists()

    if current_profile and current_profile.type != UserTypes.SUPER_ADMIN:
        new_state = (
            UserState.COMPLETE_SETUP_PROFILE
            if is_setup_profile
            else UserState.PENDING_SETUP_PROFILE
        )
        current_profile.state = new_state
        current_profile.save()


def get_active_profile_id(request):
    user_company_profile_id = request.auth.payload.get("user_company_profile_id", None)
    if not user_company_profile_id:
        user_agent = get_user_agent_info(request.user, request)
        user_company_profile_id = (
            user_agent.get("user_company_profile_id") if user_agent else None
        )

    current_profile = request.user.user_company_profile_user.filter(
        id=user_company_profile_id, status=ProfileStatus.ACTIVE
    ).last()
    current_active_profile_auth = (
        request.auth.payload.get("profile_id", None) if request else None
    )
    active_profile_id = None
    if current_active_profile_auth:
        active_profile_id = current_active_profile_auth
    elif not current_active_profile_auth and current_profile:
        active_profile_id = current_profile.profile_id
    return active_profile_id, user_company_profile_id


def set_active_profile(self, data):
    active_profile_id, _ = get_active_profile_id(self.context.get("request", None))
    data["user_profile"] = active_profile_id
    return data


def get_operator_roles(perm_type):
    pass


def get_full_name(first_name, last_name):
    """
    Return the first_name plus the last_name, with a space in between.
    """
    full_name = "%s %s" % (first_name, last_name)
    return full_name.strip()


def get_default_role(code):
    from apps.auth_oauth.models.role_model import Role

    return Role.objects.filter(code=code)

def force_logout_and_clear_tokens(request, response):
    """
    Revoke access + refresh tokens and clear cookies.
    Uses same logic as LogoutView but works inside any view.
    """

    # Get refresh token from cookie
    refresh_token = request.COOKIES.get(
        settings.SIMPLE_JWT["REFRESH_COOKIE"], None
    )

    if refresh_token:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            delete_cached_key(f"refresh_jti:{token['jti']}")
        except TokenError:
            pass  # ignore invalid refresh token

    # Revoke access token
    try:
        revoke_access_token(request, settings.SIMPLE_JWT["VERIFYING_KEY"])
    except Exception:
        pass

    # Clear cookies
    del_jwt_response_cookie(response)

    return response