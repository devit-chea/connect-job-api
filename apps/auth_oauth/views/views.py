import logging
from datetime import datetime
from datetime import timedelta

import unicodedata
from django.conf import settings
from django.contrib.auth import (
    authenticate,
)
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.password_validation import (
    validate_password,
    get_password_validators,
)
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_rest_passwordreset.models import (
    ResetPasswordToken,
    clear_expired,
    get_password_reset_token_expiry_time,
    get_password_reset_lookup_field,
)
from django_rest_passwordreset.serializers import (
    EmailSerializer,
    PasswordTokenSerializer,
    ResetTokenSerializer,
)
from django_rest_passwordreset.signals import (
    reset_password_token_created,
    pre_password_reset,
)
from rest_framework import exceptions
from rest_framework import generics
from rest_framework import serializers
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.auth_oauth.constants.auth_constants import (
    UserStatus,
    UserState,
    UserTypes, ProfileStatus,
)
from apps.auth_oauth.mixins.encryption_mixins import EncryptionMixin
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.models.permission_model import Permission
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.auth_oauth.serializers.auth_serializer import (
    UserSerializer,
    LoginForm,
    LoginSerializer,
    ChangePasswordSerializer,
    ResetPasswordRequestTokenInherit,
    OperatorUserCreateSerializer,
    ApplicantUserUpdateSerializer,
    ResetPasswordChangePasswordSerializer,
    EnabledUserSerializer,
    CurrentUserSerializer,
    SwitchProfileSerializer,
    PermissionSerializer, ResetPasswordForgotPasswordSerializer,
)
from apps.auth_oauth.services.permission_service import PermissionService
from apps.auth_oauth.services.user_company_profile_service import (
    UserCompanyProfileService,
)
from apps.auth_oauth.utils.auth_util import (
    del_jwt_response_cookie,
    force_logout_and_clear_tokens,
)
from apps.auth_oauth.utils.altcha_util import verify_altcha_or_none
from apps.auth_oauth.utils.auth_util import del_jwt_response_cookie
from apps.auth_oauth.utils.auth_util import get_user_agent_info
from apps.auth_oauth.utils.auth_util import set_jwt_response_cookie
from apps.auth_oauth.utils.rate_limit import rate_limit, rate_limit_sliding
from apps.auth_oauth.utils.token import issue_token_to_user, logout_util
from apps.auth_totp_mail.utils import email as Email, email
from apps.auth_totp_mail.utils.commons import validate_single_use_token, mark_as_used
from apps.auth_totp_mail.utils.commons import validate_single_use_token
from apps.base.mixins.permission_mixin import PermissionMixin
from apps.base.utils.base64image_util import Base64ImageUtil
from apps.base.views.base_views import BaseListAPIView
from apps.base.views.base_views import BaseUpdateAPIView
from apps.base.views.sys_setting_view import SysSettingViewByName
from apps.core.exceptions.base_exceptions import (
    BadRequestException,
    PermissionDeniedException,
)
from config.settings.base import TWO_STEP_VERIFICATION
from apps.base.decorators.permission_decorator import permission

logger = logging.getLogger(__name__)

FAIL_RESET_PASS_MSG = "If an account exists for that email, a reset link will be sent."
PERMISSION_FIELDS = ["id", "name", "codename", "type", "group"]
encryption = EncryptionMixin()
require_two_step_verification_types = {UserTypes.RECRUITER, UserTypes.ADMIN_RECRUITER, UserTypes.SUPER_ADMIN}


class PermissionView(BaseListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PermissionSerializer

    filterset_fields = PERMISSION_FIELDS
    search_fields = PERMISSION_FIELDS
    ordering_fields = PERMISSION_FIELDS

    queryset = Permission.objects.filter(parent__isnull=True)

    RECRUITER_GROUPS = {"recruiter", "admin_recruiter"}

    @permission(
        permission_codename=[
            "operator_manage_role",
            "admin_recruiter_manage_role",
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        user_type = getattr(self.request, "user_type", None)

        if user_type == UserTypes.SUPER_ADMIN.value:
            return qs

        if user_type == UserTypes.ADMIN_RECRUITER.value:
            return self._filter_recruiter_permissions(qs)

        raise PermissionDeniedException()

    def _filter_recruiter_permissions(self, queryset):
        """
        Admin recruiter can only see recruiter-related permissions
        """
        return queryset.filter(
            group__in=self.RECRUITER_GROUPS
        ).distinct()


class PermissionUserView(BaseListAPIView):
    filterset_fields = PERMISSION_FIELDS
    search_fields = PERMISSION_FIELDS
    ordering_fields = PERMISSION_FIELDS
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer

    def list(self, request, *args, **kwargs):
        queryset, context = PermissionService().get_user_roles_and_permissions(request)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True, context=context)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True, context=context)
        return Response(serializer.data)


class MobileLoginView(generics.CreateAPIView):
    permission_classes = ()
    serializer_class = LoginSerializer
    http_method_names = ["post"]

    def create(self, request, *args, **kwargs):
        # call login
        request.data["type"] = UserTypes.APPLICANT.value
        return LoginView().post(request, *args, **kwargs)


class SwitchProfileView(BaseUpdateAPIView):
    queryset = UserCompanyProfile.objects.order_by("id")
    serializer_class = SwitchProfileSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.user != request.user:
            raise BadRequestException(f"Your profile {kwargs.get('pk')} is not found.")
        return issue_token_to_user(
            request=request, user=request.user, user_company_profile_id=instance.pk
        )


class ApplicantUserUpdateView(generics.UpdateAPIView):
    queryset = User.objects.order_by("id")
    serializer_class = ApplicantUserUpdateSerializer

    @transaction.atomic()
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        validated_data = serializer.validated_data
        validated_file = validated_data.get("file")
        request_file = request.data.get("file")
        ref_id = instance.pk
        ref_type = "user_profile"
        Base64ImageUtil.update_base64image(
            validated_file, request_file, ref_id, ref_type
        )
        return Response(serializer.data)


class RefreshTokenView(TokenRefreshView):

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            request.data["refresh"] = request.COOKIES.get(
                settings.SIMPLE_JWT["REFRESH_COOKIE"], "no_token"
            )

        response = super().post(request, *args, **kwargs)
        set_jwt_response_cookie(
            response,
            response.data["access"],
            response.data["refresh"],
        )

        return response


class CurrentUserView(PermissionMixin, APIView):
    permission_classes = [IsAuthenticated]
    allow_pending_profile = True
    permission_codename = [
        "operator_manage_profile",
        "recruiter_manage_profile",
        "applicant_manage_profile",
        "admin_recruiter_manage_profile"
    ]

    def get(self, request):
        if request.user.is_anonymous:
            return Response({"is_anonymous": True})
        user_agent = get_user_agent_info(request.user, request)
        serializer = CurrentUserSerializer(
            request.user, context={"request": request, "user_agent": user_agent}
        )
        return Response(serializer.data)


# check authorization
class CheckAuthView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get(self, request, *args, **kwargs):
        return Response("Success")


class LoginView(generics.CreateAPIView):
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
            encryption = EncryptionMixin()
            password = encryption.decrypt_value(encrypted_password)
        except Exception:
            raise serializers.ValidationError(
                {"detail": message_invalid_user}
            )

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
        default_ucp_id = user.default_user_profile_company
        if profile_type:
            # type applicant only for user
            user_profile_applicant = UserCompanyProfileService().get_by_userid(
                user.pk, profile_type
            )
            if not user_profile_applicant:
                return Response(
                    data={"detail": "Mobile only support applicant."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            request.data["user_company_profile_id"] = user_profile_applicant.pk
        else:
            if default_ucp_id:
                request.data["user_company_profile_id"] = default_ucp_id

        if user.is_disable:
            return Response(
                data={"detail": "User have disable"}, status=status.HTTP_423_LOCKED
            )

        elif user and user.login_type == "pwd":
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
                is_require_two_step_verification = user.user_company_profile_user.filter(
                    type__in=require_two_step_verification_types
                ).exists()
                if user.is_active:
                    response = self.login_cookie(request, user, is_require_two_step_verification)
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
            return email.is_required_email_confirm_login(request, user)

        # END MAIL OPT
        # else:
        #   Logined without confirm 2-step verification

        return issue_token_to_user(request=request, user=user)


class LogoutApi(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = getattr(request, "user", None)
        response = logout_util(request, user)

        self.try_cookie_logout(request, response)
        return response

    @staticmethod
    def try_cookie_logout(request, response):
        try:
            refresh_token = request.COOKIES.get(
                settings.SIMPLE_JWT["REFRESH_COOKIE"], "no_token"
            )

            token = RefreshToken(refresh_token)
            token.blacklist()
            del_jwt_response_cookie(response)
        except Exception:
            pass


class ChangePassWordApi(generics.CreateAPIView):
    permission_classes = []
    serializer_class = ChangePasswordSerializer

    def post(self, request: Request):
        user = request.user
        encrypted_old_password = request.data.get("old_password")
        encrypted_new_password1 = request.data.get("new_password1")
        encrypted_new_password2 = request.data.get("new_password2")

        old_password = encryption.decrypt_value(encrypted_old_password)
        new_password1 = encryption.decrypt_value(encrypted_new_password1)
        new_password2 = encryption.decrypt_value(encrypted_new_password2)
        decrypted_data = {
            "old_password": old_password,
            "new_password1": new_password1,
            "new_password2": new_password2,
        }
        form = PasswordChangeForm(user, decrypted_data)
        invalid_data = {"form_errors": {}, "errors": {}}
        invalid_data["form_errors"] = form.errors
        exception = {"error": invalid_data}
        if form.is_valid():
            default_password = SysSettingViewByName.get_setting(
                self, "DEFAULT_PASSWORD", company=user.base_company
            )
            if request.data.get("old_password") == request.data.get("new_password1"):
                invalid_data["form_errors"] = {
                    "message": "You used this password recently. Please choose a different one"
                }
                return Response(
                    data=exception, status=status.HTTP_422_UNPROCESSABLE_ENTITY
                )

            if request.data.get("new_password1") == default_password:
                invalid_data["form_errors"] = {
                    "message": ["You can't use this password"]
                }
                return Response(
                    data=exception, status=status.HTTP_422_UNPROCESSABLE_ENTITY
                )

            form.user.password_expired = datetime.now()
            form.save()
            # request.user.auth_token.delete()
            return Response(
                data={"message": "Your password has been changed"}, status=status.HTTP_200_OK
            )
        else:
            return Response(data=exception, status=status.HTTP_422_UNPROCESSABLE_ENTITY)


class UnLockUserApi(APIView):
    permission_classes = []

    def post(self, request, pk):
        user = User.objects.get(id=pk)

        if user:
            pass_expire_minute = SysSettingViewByName.get_setting(
                self, "PASSWORD_EXPIRE_MINUTES", company=None, user=user.id
            )
            password_expired = user.password_expired + timedelta(
                minutes=int(pass_expire_minute)
            )

            if user.is_lock or user.is_password_expired:
                user.is_active = True
                user.status = "active"
                user.is_lock = False

            elif user.is_active == True:
                return Response(
                    data=f"User {user} haven't locked", status=status.HTTP_200_OK
                )
            elif (
                    password_expired <= datetime.now().astimezone()
                    and user.is_password_expired
            ):
                user.status = "password_expired"
                user.is_expired = True
                user.is_lock = False

            user.count_fail = 0
            user.save()
            return Response(data="User {user} have unlocked", status=status.HTTP_200_OK)
        else:
            return Response(
                data="User {pk} Not Found", status=status.HTTP_404_NOT_FOUND
            )


class DisableUserApi(generics.UpdateAPIView):
    permission_classes = ()
    serializer_class = EnabledUserSerializer

    def update(self, request, *args, **kwargs):
        pk = kwargs.get("pk", None)
        user = User.objects.get(id=pk)
        if user:
            if user.is_disable == True:
                return Response(
                    data=f"User {pk} have disable", status=status.HTTP_200_OK
                )
            else:
                user.is_disable = True
                user.is_active = False
                user.status = "disable"

            user.save()
            return Response(data=f"User {pk} have disable", status=status.HTTP_200_OK)
        else:
            return Response(
                data=f"User {pk} Not Found", status=status.HTTP_404_NOT_FOUND
            )


class EnableUserApi(generics.UpdateAPIView):
    permission_classes = ()
    serializer_class = EnabledUserSerializer

    def update(self, request, *args, **kwargs):
        pk = kwargs.get("pk", None)
        user = User.objects.get(id=pk)
        invalid_data = {"form_errors": {}, "errors": {}}
        if user:
            if user.is_disable == False:
                return Response(
                    data=f"User {pk} have enable", status=status.HTTP_200_OK
                )
            else:
                user.is_disable = False
                user.is_active = True
                user.status = "active"
            user.save()
            return Response(data=f"User {pk} have enable", status=status.HTTP_200_OK)
        else:
            return Response(
                data=f"User {pk} Not Found", status=status.HTTP_404_NOT_FOUND
            )


def _unicode_ci_compare(s1, s2):
    """
    Perform case-insensitive comparison of two identifiers, using the
    recommended algorithm from Unicode Technical Report 36, section
    2.11.2(B)(2).
    """
    normalized1 = unicodedata.normalize("NFKC", s1)
    normalized2 = unicodedata.normalize("NFKC", s2)

    return normalized1.casefold() == normalized2.casefold()


class ResetPasswordRequestToken(generics.CreateAPIView):
    """
    An Api View which provides a method to request a password reset token based on an e-mail address

    Sends a signal reset_password_token_created when a reset token was created
    """

    throttle_classes = ()
    permission_classes = ()
    serializer_class = EmailSerializer
    authentication_classes = ()

    def post(self, request, *args, **kwargs):

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        # before we continue, delete all existing expired tokens
        password_reset_token_validation_time = get_password_reset_token_expiry_time()

        # datetime.now minus expiry hours
        now_minus_expiry_time = timezone.now() - timedelta(
            hours=password_reset_token_validation_time
        )

        # delete all tokens where created_at < now - 24 hours
        clear_expired(now_minus_expiry_time)

        # find a user by email address (case insensitive search)
        users = User.objects.filter(
            **{"{}__iexact".format(get_password_reset_lookup_field()): email}
        )
        active_user_found = False

        for user in users:
            if user.eligible_for_reset():
                active_user_found = True
                break

        # No active user found, raise a validation error
        # but not if DJANGO_REST_PASSWORDRESET_NO_INFORMATION_LEAKAGE == True
        if not active_user_found and not getattr(
                settings, "DJANGO_REST_PASSWORDRESET_NO_INFORMATION_LEAKAGE", False
        ):
            raise exceptions.ValidationError(
                {
                    "email": [
                        _(
                            FAIL_RESET_PASS_MSG
                        )
                    ],
                }
            )

        # last but not least: iterate over all users that are active and can change their password
        # and create a Reset Password Token and send a signal with the created token
        for user in users:
            if user.eligible_for_reset() and _unicode_ci_compare(
                    email, getattr(user, get_password_reset_lookup_field())
            ):
                # define the token as none for now
                token = None

                # check if the user already has a token
                if user.password_reset_tokens.all().count() > 0:
                    # yes, already has a token, re-use this token
                    token = user.password_reset_tokens.all()[0]
                else:
                    # no token exists, generate a new token
                    token = ResetPasswordToken.objects.create(
                        user=user,
                    )
                # send a signal that the password token was created
                # let whoever receives this signal handle sending the email for the password reset
                reset_password_token_created.send(
                    sender=self.__class__,
                    instance=self,
                    reset_password_token=token,
                    request=request,
                )

        return Response({"status": "OK"})


class ResetPasswordValidateToken(GenericAPIView):
    """
    An Api View which provides a method to verify that a token is valid
    """

    throttle_classes = ()
    permission_classes = ()
    serializer_class = ResetTokenSerializer
    authentication_classes = ()

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({"status": "OK"})


class ResetPasswordView(generics.CreateAPIView):
    permission_classes = ()
    serializer_class = EmailSerializer
    authentication_classes = ()

    def create(self, request, *args, **kwargs):
        altcha = request.data.get("altcha")
        ok, _ = verify_altcha_or_none(altcha)

        if not ok:
            return Response(
                {"detail": FAIL_RESET_PASS_MSG},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        password_reset_token_validation_time = get_password_reset_token_expiry_time()

        # datetime.now minus expiry hours
        now_minus_expiry_time = timezone.now() - timedelta(
            hours=password_reset_token_validation_time
        )

        # delete all tokens where created_at < now - 24 hours

        clear_expired(now_minus_expiry_time)
        user = (
            User.objects.filter(
                ~Q(state=UserState.PENDING_VERIFY_OPT),
                **{
                    "{}__iexact".format(get_password_reset_lookup_field()): email,
                    "status": UserStatus.ACTIVE,
                },
            )
            .order_by("-id")
            .first()
        )

        if not user:
            raise BadRequestException(
                FAIL_RESET_PASS_MSG
            )
        if user.eligible_for_reset():
            return Email.is_required_email_confirm_login(request, user)

        return Response({"detail": FAIL_RESET_PASS_MSG}, status=400)


class ResetPasswordChangePasswordView(generics.CreateAPIView):
    serializer_class = ResetPasswordForgotPasswordSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        encrypted_password = serializer.validated_data["password"]
        encrypted_password_confirm = serializer.validated_data["password_confirm"]

        password = encryption.decrypt_value(encrypted_password)
        password_confirm = encryption.decrypt_value(encrypted_password_confirm)
        reset_token = serializer.validated_data["reset_token"]

        if password != password_confirm:
            raise BadRequestException("password not match.")
        try:
            user_id = validate_single_use_token(reset_token)
        except ValueError as e:
            logger.warning(
                "Reset password token validation failed",
                extra={
                    "error": str(e),
                    "reset_token": reset_token[:10]
                }
            )
            return Response({"detail": "Failed to reset password."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.error(
                "User not found during password reset",
                extra={"user_id": user_id}
            )
            return Response({"detail": "Failed to reset password"}, status=status.HTTP_400_BAD_REQUEST)


        if user.is_lock:
            raise BadRequestException("User Have been Locked")

        # TODO: check default_password
        # check old password 'user and new password must be different
        user_authenticated = authenticate(username=user.username, password=password)
        if user_authenticated:
            raise BadRequestException(
                "You used this password recently. Please choose a different one"
            )
        try:
            # validate the password against existing validators
            validate_password(
                password,
                user=user,
                password_validators=get_password_validators(
                    settings.AUTH_PASSWORD_VALIDATORS
                ),
            )
        except ValidationError as e:
            # raise a validation error for the serializer
            raise exceptions.ValidationError({"password": e.messages})
        user.set_password(password)
        user.is_active = True
        user.is_expired = False
        user.is_login = True
        user.login_type = "pwd"
        user.is_required_reset_pwd = False
        user.save()
        try:
            mark_as_used(reset_token)
        except Exception as e:
            logger.error(
                "Failed to consume reset token after successful password change",
                extra={"user_id": user.id, "error": str(e)},
            )
        return Response({"message": "Password reset successful."})


class ChangePasswordView(generics.CreateAPIView):
    serializer_class = ResetPasswordChangePasswordSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        encrypted_password = serializer.validated_data["password"]
        encrypted_password_confirm = serializer.validated_data["password_confirm"]
        password =  encryption.decrypt_value(encrypted_password)
        password_confirm =  encryption.decrypt_value(encrypted_password_confirm)

        if password != password_confirm:
            raise BadRequestException("password not match.")

        user = User.objects.filter(pk=request.user.pk).first()

        if user:
            if not user.is_required_reset_pwd:
                raise BadRequestException("User does not require a password change.")
            if user.is_lock:
                raise BadRequestException("User Have been Locked")

            # TODO: check default_password
            # check old password 'user and new password must be different
            user_authenticated = authenticate(username=user.username, password=password)
            if user_authenticated:
                raise BadRequestException(
                    "You used this password recently. Please choose a different one"
                )
            try:
                # validate the password against existing validators
                validate_password(
                    password,
                    user=user,
                    password_validators=get_password_validators(
                        settings.AUTH_PASSWORD_VALIDATORS
                    ),
                )
            except ValidationError as e:
                # raise a validation error for the serializer
                raise exceptions.ValidationError({"password": e.messages})
            user.set_password(password)
            user.is_active = True
            user.is_expired = False
            user.is_login = True
            user.login_type = "pwd"
            user.is_required_reset_pwd = False
            user.save()

        response = Response({"message": "Password reset successful."})
        force_logout_and_clear_tokens(request, response)
        return response


class AdminLoginView(LoginView):
    pass
