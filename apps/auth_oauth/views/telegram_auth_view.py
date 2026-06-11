import base64
import hashlib
import json
import logging
import secrets
from datetime import datetime
from datetime import timedelta
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.contrib.auth import (
    authenticate,
)
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from django_rest_passwordreset.models import (
    clear_expired,
    get_password_reset_token_expiry_time,
)
from rest_framework import generics
from rest_framework import serializers
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auth_oauth.constants.auth_constants import (
    UserState,
)
from apps.auth_oauth.constants.auth_constants import (
    UserTypes,
    UserStatus,
)
from apps.auth_oauth.mixins.encryption_mixins import EncryptionMixin
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.serializers.auth_serializer import (
    UserSerializer,
    LoginForm,
    LoginSerializer,
    ResetPasswordRequestTokenInherit,
    TelegramResetPasswordSerializer,
)
from apps.auth_oauth.serializers.recruiter_serializer import TelegramSignupSerializer
from apps.auth_oauth.serializers.social_serializer import TelegramCallbackSerializer
from apps.auth_oauth.services.telegram_authn_service import (
    TelegramAuthNService,
    TelegramAuthNError,
)
from apps.auth_oauth.services.telegram_otp_service import (
    resolve_link_token,
    revoke_link_token,
    send_otp_via_telegram,
    generate_telegram_link_token,
    build_telegram_deep_link,
)
from apps.auth_oauth.services.user_company_profile_service import (
    UserCompanyProfileService,
)
from apps.auth_oauth.utils.auth_util import (
    redirect_to_frontend,
)
from apps.auth_oauth.utils.rate_limit import rate_limit
from apps.auth_oauth.utils.token import issue_token_to_user
from apps.auth_oauth.views.views import FAIL_RESET_PASS_MSG
from apps.auth_totp_mail.models.mail_template_models import EmailManager
from apps.auth_totp_mail.utils import telegram
from apps.auth_totp_mail.utils.commons import retry_in_to_timestamp
from apps.base.views.base_views import BaseCreateAPIView
from apps.base.views.sys_setting_view import SysSettingViewByName
from apps.core.exceptions.base_exceptions import BadRequestException
from config.settings.base import TWO_STEP_VERIFICATION

logger = logging.getLogger(__name__)


encryption = EncryptionMixin()
require_two_step_verification_types = {
    UserTypes.RECRUITER,
    UserTypes.ADMIN_RECRUITER,
    UserTypes.SUPER_ADMIN,
    # UserTypes.APPLICANT
}
_PKCE_TTL = 600


def _generate_pkce() -> tuple:
    """Returns (code_verifier, code_challenge)."""
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


def _decode_state(state: str) -> dict:
    """
    State is base64-encoded JSON: {"nonce": "...", "redirect_uri": "..."}.
    """
    try:
        return json.loads(base64.urlsafe_b64decode(state + "=="))
    except Exception:
        return {}


def _deep_link_redirect(url: str) -> HttpResponse:
    response = HttpResponse(status=302)
    response["Location"] = url
    return response


def _is_web(redirect_uri: str) -> bool:
    return urlparse(redirect_uri).scheme.lower() in ("http", "https")

class RecruiterTelegramSignupView(CreateAPIView):
    """
    API for recruiter normal signup user
    """

    permission_classes = ()
    queryset = User.objects.all()
    serializer_class = TelegramSignupSerializer

    @rate_limit("signup_recruiter")
    def create(self, request, *args, **kwargs):
        # altcha = request.data.get("altcha")
        # ok, _ = verify_altcha_or_none(altcha)
        #
        # if not ok:
        #     return Response(
        #         {"detail": "Unable to create the account."},
        #         status=status.HTTP_400_BAD_REQUEST,
        #     )
        request.META.setdefault("HTTP_USER_AGENT", "TelegramBot")
        request.META.setdefault("REMOTE_ADDR", "0.0.0.0")
        request.META.setdefault("HTTP_X_FORWARDED_FOR", "0.0.0.0")

        serializer = self.get_serializer(
            data=request.data, profile_type=UserTypes.ADMIN_RECRUITER.value
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        totp, otp = EmailManager.issue_telegram_otp(instance, request)
        token = generate_telegram_link_token(instance, otp)
        deep_link = build_telegram_deep_link(token)

        return Response(
            {
                "status": "pending_telegram_link",
                "message": "Open Telegram and start the bot to receive your OTP.",
                "telegram_link": deep_link,
                "token": totp.confirm_key,
                "expire_in": totp.otp_expiry,
                "retry_in": retry_in_to_timestamp(totp.company_id),
            },
            status=status.HTTP_200_OK,
        )


class ApplicantTelegramSignupView(BaseCreateAPIView):
    permission_classes = ()
    queryset = User.objects.all()
    serializer_class = TelegramSignupSerializer

    def create(self, request, *args, **kwargs):
        request.META.setdefault("HTTP_USER_AGENT", "TelegramBot")
        request.META.setdefault("REMOTE_ADDR", "0.0.0.0")
        request.META.setdefault("HTTP_X_FORWARDED_FOR", "0.0.0.0")
        # altcha = request.data.get("altcha", "")
        # ok, _ = verify_altcha_or_none(altcha)
        # if not ok:
        #     return Response(
        #         {"detail": "Unable to create the account."},
        #         status=status.HTTP_400_BAD_REQUEST,
        #     )

        serializer = self.get_serializer(
            data=request.data,
            profile_type=UserTypes.APPLICANT.value,
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        totp, otp = EmailManager.issue_telegram_otp(instance, request)
        token = generate_telegram_link_token(instance, otp)
        deep_link = build_telegram_deep_link(token)

        return Response(
            {
                "status": "pending_telegram_link",
                "message": "Open Telegram and start the bot to receive your OTP.",
                "telegram_link": deep_link,
                "token": totp.confirm_key,
                "expire_in": totp.otp_expiry,
                "retry_in": retry_in_to_timestamp(totp.company_id),
            },
            status=status.HTTP_200_OK,
        )


class TelegramBotWebhookView(APIView):
    permission_classes = ()

    def post(self, request, *args, **kwargs):
        request.META.setdefault("HTTP_USER_AGENT", "TelegramBot")
        request.META.setdefault("REMOTE_ADDR", "0.0.0.0")
        request.META.setdefault("HTTP_X_FORWARDED_FOR", "0.0.0.0")
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if secret != settings.TELEGRAM_WEBHOOK_SECRET:
            return Response({"ok": False}, status=status.HTTP_403_FORBIDDEN)
        logger.info("Telegram Webhook called.")
        message = request.data.get("message", {})
        text = message.get("text", "").strip()
        chat_id = str(message.get("chat", {}).get("id", ""))

        if not text.startswith("/start"):
            return Response({"ok": True})

        parts = text.split(maxsplit=1)
        token = parts[1].strip() if len(parts) > 1 else None

        if not token:
            return Response({"ok": True})
        # todo replace back
        # data = resolve_link_token(token)
        # if not data:
        #     logger.info("Telegram sent failed::::::")
        #     return Response({"ok": True})
        # user_id = data["user_id"]
        # otp = data["cf_key"]
        otp = "168168"
        try:
            # todo take fixed user
            # user = User.objects.get(pk=user_id, is_active=True)
            user = User.objects.filter(is_active=True).order_by("-pk").first()
        except User.DoesNotExist:
            return Response({"ok": True})

        if (
            User.objects.filter(telegram_chat_id=chat_id, is_active=True)
            .exclude(pk=user.pk)
            .exists()
        ):
            return Response({"ok": True})

        # Save chat_id, clear token
        User.objects.filter(pk=user.pk).update(
            telegram_chat_id=chat_id,
            telegram_link_token=None,
        )
        # todo uncomment
        # revoke_link_token(token)

        if user.state == UserState.PENDING_VERIFY_OPT:
            sent = send_otp_via_telegram(chat_id, otp)
            logger.info(f"Sent otp status:::: {sent}")
        return Response({"ok": True})


class TelegramLoginView(generics.CreateAPIView):
    permission_classes = ()
    serializer_class = LoginSerializer
    http_method_names = ["post"]

    def post(self, request: Request, *args, **kwargs):
        form = LoginForm(request.data)
        time_fail_minutes = 0
        message_invalid_user = "Invalid username or password"
        if not form.is_valid():
            return Response(
                data=form.errors, status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        username = form.cleaned_data.get("username")
        encrypted_password = form.cleaned_data.get("password")

        try:
            password = encryption.decrypt_value(encrypted_password)
        except Exception:
            raise serializers.ValidationError({"detail": message_invalid_user})

        user = (
            User.objects.filter(
                username=username, status=UserStatus.ACTIVE, is_active=True
            )
            .order_by("-id")
            .first()
        )
        if not user:
            return Response(
                data={"detail": message_invalid_user},
                status=status.HTTP_400_BAD_REQUEST,
            )
        profile_type = request.data.get("type", None)
        if profile_type:
            # type applicant only for user
            user_profile_applicant = UserCompanyProfileService().get_by_userid(
                user.pk, profile_type
            )
            if not user_profile_applicant:
                return Response(
                    data={"detail": "mobile only support applicant."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            request.data["user_company_profile_id"] = user_profile_applicant.pk

        if user.is_disable:
            return Response(
                data={"detail": "User have disable"}, status=status.HTTP_423_LOCKED
            )

        elif user and user.login_type == "telegram":
            time_reset = SysSettingViewByName.get_setting(
                self, "TIME_RESET_FAIL_LOGIN_MINUTES", company=None, user=user
            )
            pass_expire_minute = SysSettingViewByName.get_setting(
                self, "PASSWORD_EXPIRE_MINUTES", company=None, user=user
            )
            fail_login_count = SysSettingViewByName.get_setting(
                self, "FAIL_LOGIN_COUNT", company=None, user=user
            )
            if user.last_fail:
                time_fail_seconds = (
                    datetime.now().astimezone() - user.last_fail
                ).seconds
                time_fail_minutes, _ = divmod(time_fail_seconds, 60)

            user = authenticate(username=username, password=password)
            if user:
                if user.state == UserState.PENDING_VERIFY_OPT:
                    return Response(
                        data={"detail": "User is pending verify otp"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                password_expired = user.password_expired + timedelta(
                    minutes=int(pass_expire_minute)
                )
                if not user.is_superuser:
                    if user.is_active == False and not user.is_password_expired:
                        user.is_active = True

                    if user.is_lock and user.is_password_lock:
                        if time_fail_minutes >= int(time_reset):
                            self.check_is_time_reset_password(user)
                            if (
                                password_expired <= datetime.now().astimezone()
                                and user.is_password_expired
                            ):
                                return self.check_is_password_expired(user)
                        else:
                            return Response(
                                data={"detail": "User is lock"},
                                status=status.HTTP_423_LOCKED,
                            )

                    if (
                        user.is_active == False
                        and user.is_password_expired
                        and password_expired >= datetime.now().astimezone()
                    ):
                        user.is_active = True

                    elif (
                        password_expired <= datetime.now().astimezone()
                        and user.is_password_expired
                    ):
                        return self.check_is_password_expired(user)
                is_require_two_step_verification = (
                    user.user_company_profile_user.filter(
                        type__in=require_two_step_verification_types
                    ).exists()
                )
                if user.is_active:
                    response = self.login_cookie(
                        request, user, is_require_two_step_verification
                    )
                    user.status = UserStatus.ACTIVE
                    user.is_login = True
                    user.is_pending_verification = is_require_two_step_verification
                    user.save()
                    return response
            else:
                if user and not user.is_superuser and user.is_password_lock:
                    if time_fail_minutes >= int(time_reset):
                        self.check_is_time_reset_password(user)

                    elif not user.count_fail:
                        user.count_fail = 1
                    else:
                        user.count_fail += 1
                        if user.count_fail >= int(fail_login_count):
                            user.is_active = False
                            user.count_fail += 1
                            user.status = "lock"
                            user.is_lock = True
                            user.last_fail = datetime.now()
                            user.save()
                            return Response(
                                data={"detail": "User is lock"},
                                status=status.HTTP_423_LOCKED,
                            )
                    user.last_fail = datetime.now()
                    user.save()
                return Response(
                    data={"detail": message_invalid_user},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return Response(
            data={
                "detail": "Invalid username or password",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    def check_is_password_expired(self, user):
        user.is_active = False
        user.is_expired = True
        user.status = "password_expired"
        user.save()
        token = ResetPasswordRequestTokenInherit.post(self, request=user.email)
        return Response(
            data={
                "message": "Password Expired",
                "token": token.key,
                "status": user.status,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    def check_is_time_reset_password(self, user):
        user.is_active = True
        user.is_lock = False
        user.status = "active"
        user.count_fail = 0

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def login_cookie(self, request, user, is_require_two_step_verification):
        user_type = request.data.get("type")
        if (
            is_require_two_step_verification
            and TWO_STEP_VERIFICATION
            and user_type != UserTypes.APPLICANT.value
            and user_type is None
        ):
            # Logined but required 2-step verification
            return telegram.is_required_telegram_confirm_login(request, user)

        return issue_token_to_user(request=request, user=user)


class TelegramResetPasswordView(generics.CreateAPIView):
    permission_classes = ()
    authentication_classes = ()
    serializer_class = TelegramResetPasswordSerializer

    @rate_limit("reset_password")
    def create(self, request, *args, **kwargs):
        request.META.setdefault("HTTP_USER_AGENT", "TelegramBot")
        request.META.setdefault("REMOTE_ADDR", "0.0.0.0")
        request.META.setdefault("HTTP_X_FORWARDED_FOR", "0.0.0.0")

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone_number"]

        password_reset_token_validation_time = get_password_reset_token_expiry_time()
        now_minus_expiry_time = timezone.now() - timedelta(
            hours=password_reset_token_validation_time
        )
        clear_expired(now_minus_expiry_time)

        user = (
            User.objects.filter(
                ~Q(state=UserState.PENDING_VERIFY_OPT),
                phone_number=phone_number,
                login_type="telegram",
                status=UserStatus.ACTIVE,
                is_active=True,
            )
            .order_by("-id")
            .first()
        )

        if not user:
            raise BadRequestException(FAIL_RESET_PASS_MSG)

        if not user.eligible_for_reset():
            return Response({"detail": FAIL_RESET_PASS_MSG}, status=400)

        totp_mail, otp = EmailManager.issue_telegram_otp(user, request)

        if user.telegram_chat_id:
            send_otp_via_telegram(user.telegram_chat_id, otp)
            return Response(
                {
                    "status": "confirm_otp",
                    "message": "Please confirm your OTP to continue.",
                    "token": totp_mail.confirm_key,
                    "expire_in": totp_mail.otp_expiry,
                    "retry_in": retry_in_to_timestamp(totp_mail.company_id),
                },
                status=status.HTTP_200_OK,
            )
        # todo can check user_telegram contact number for link chat_id
        return Response({"detail": FAIL_RESET_PASS_MSG}, status=400)


class TelegramAuthorizeView(APIView):
    """
    GET /api/auth/telegram/authorize

    Required query params: state, code_challenge, code_challenge_method=S256
    Accepted but unused at Telegram level: client_id, redirect_uri, response_type, scope
    """

    permission_classes = []
    authentication_classes = ()

    def get(self, request, *args, **kwargs):
        state = request.query_params.get("state", "").strip()
        code_challenge = request.query_params.get("code_challenge", "").strip()
        code_challenge_method = request.query_params.get(
            "code_challenge_method", ""
        ).strip()

        if not state or not code_challenge:
            return Response(
                {
                    "error": "invalid_request",
                    "error_description": ("Missing required PKCE parameters "),
                },
                status=400,
            )
        state_data = _decode_state(state)
        redirect_uri = state_data.get("redirect_uri", "")
        nonce = state_data.get("nonce", "")

        if _is_web(redirect_uri):
            if not nonce:
                return Response(
                    {
                        "error": "invalid_request",
                        "error_description": "state must contain nonce for web flow",
                    },
                    status=400,
                )
            code_verifier, code_challenge = _generate_pkce()
            cache.set(f"telegram_pkce:{nonce}", code_verifier, timeout=_PKCE_TTL)
        url = TelegramAuthNService.build_telegram_auth_url(
            state=state,
            code_challenge=code_challenge,
        )
        return redirect(url)


class TelegramOAuthCallbackView(APIView):
    """
    GET /api/auth/telegram/callback

    Telegram redirects here after the user authenticates (this URL is
    TELEGRAM_REDIRECT_URI registered with Telegram).
    """

    permission_classes = []
    authentication_classes = ()

    def get(self, request, *args, **kwargs):
        code = request.query_params.get("code", "").strip()
        state = request.query_params.get("state", "").strip()

        state_data = _decode_state(state) if state else {}
        client_uri = (
            state_data.get("redirect_uri") or settings.TELEGRAM_MOBILE_REDIRECT_URI
        )

        logger.warning(f"client_uri: {client_uri}")

        if not code or not state:
            error_params = urlencode(
                {
                    "error": "invalid_request",
                    "error_description": "Missing code or state",
                }
            )
            return _deep_link_redirect(f"{client_uri}?{error_params}")

        if _is_web(client_uri):
            return self._handle_web(request, code, state_data)

        params = urlencode({"code": code, "state": state})
        redirect_url = f"{client_uri}?{params}"
        logger.warning("Telegram mobile callback redirect → %s", redirect_url)
        return _deep_link_redirect(f"{client_uri}?{params}")

    def _handle_web(self, request, code: str, state_data: dict):
        nonce = state_data.get("nonce", "")
        raw_code_verifier = cache.get(f"telegram_pkce:{nonce}")

        if not raw_code_verifier:
            return redirect(f"{settings.WEB_BASE_URL_LOGIN}?error=session_expired")
        code_verifier = raw_code_verifier.decode() if isinstance(raw_code_verifier, bytes) else raw_code_verifier
        cache.delete(f"telegram_pkce:{nonce}")
        try:
            token_response = TelegramAuthNService.exchange_code(
                code, code_verifier, settings.TELEGRAM_REDIRECT_URI
            )
            claims = TelegramAuthNService.verify_id_token(token_response["id_token"])
            user = TelegramAuthNService.get_or_create_user(claims)
        except TelegramAuthNError as exc:
            logger.warning(
                "Telegram web OIDC failed (status=%s): %s", exc.status_code, exc.detail
            )
            return redirect(f"{settings.WEB_BASE_URL_LOGIN}?error=auth_failed")
        except Exception as exc:
            logger.error(
                "Unexpected error in Telegram web callback: %s", exc, exc_info=True
            )
            return redirect(f"{settings.WEB_BASE_URL_LOGIN}?error=auth_failed")

        if not user.is_active:
            return redirect(f"{settings.WEB_BASE_URL_LOGIN}?error=account_disabled")

        token_response = issue_token_to_user(request=request, user=user)
        response = redirect_to_frontend(request, token_response)
        return response


class MobileTelegramIntegrationView(CreateAPIView):
    """
    POST /api/telegram/callback

    FE / mobile completes Telegram's OIDC authorization (PKCE + redirect) and
    sends us { code, code_verifier, redirect_uri }.  We exchange the code for
    an id_token, verify it against Telegram's JWKS, get-or-create the applicant
    user, and return our RS256 JWT pair.

    Telegram login is applicant-only; no user_type parameter is accepted.
    """

    permission_classes = []
    authentication_classes = ()
    serializer_class = TelegramCallbackSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data["code"]
        code_verifier = serializer.validated_data["code_verifier"]
        redirect_uri = settings.TELEGRAM_REDIRECT_URI

        try:
            token_response = TelegramAuthNService.exchange_code(
                code, code_verifier, redirect_uri
            )
            claims = TelegramAuthNService.verify_id_token(token_response["id_token"])
            user = TelegramAuthNService.get_or_create_user(claims)
        except TelegramAuthNError as exc:
            logger.warning(
                "Telegram OIDC failed (status=%s): %s", exc.status_code, exc.detail
            )
            raise BadRequestException(exc.detail)
        except Exception as exc:
            logger.error(
                "Unexpected error in Telegram callback: %s", exc, exc_info=True
            )
            raise BadRequestException("Authentication failed.")

        if not user.is_active:
            raise BadRequestException("This account has been disabled.")

        return issue_token_to_user(request=request, user=user)


class TestFetchRedirect(APIView):
    permission_classes = []
    authentication_classes = ()

    def get(self, request, *args, **kwargs):
        return _deep_link_redirect("connectjob-dev://oauth2redirect")
