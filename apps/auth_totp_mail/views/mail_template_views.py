import logging

from django.contrib.auth.hashers import check_password
from django.db.models import F, Value
from django.utils import timezone
from rest_framework import generics, status, serializers
from rest_framework import permissions
from rest_framework.response import Response

from apps.auth_oauth.constants.auth_constants import UserStatus, UserState
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.security.asymmetric_encryption import _decrypted_password
from apps.auth_setting.config import Configs
from apps.auth_totp_mail.filters.mail_filters import MailTemplateFilter
from apps.auth_totp_mail.models.mail_template_models import EmailManager, MailTemplate
from apps.auth_totp_mail.models.mail_template_models import TotpMailConfirmation
from apps.auth_totp_mail.services.resend_otp_service import TotpResendService
from apps.auth_totp_mail.utils import commons
from apps.base.views.base_views import AdminRecruiterOrRecruiterBaseViewSet
from apps.core.exceptions.base_exceptions import (
    BadRequestException,
    NotFoundException,
    ExpiredException,
)
from config.settings.base import LIMIT_RESEND_OTP
from apps.auth_totp_mail.serializers.mail_template_serializers import (
    ConfirmSerializers,
    ResendSerializers,
    LoginResendSerializers,
    MailTemplateReadSerializer,
)
from apps.auth_totp_mail.utils.commons import generate_single_use_token
from apps.auth_totp_mail.utils.email import mask_email
from apps.auth_oauth.mixins.encryption_mixins import EncryptionMixin
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import (
    validate_password,
    get_password_validators,
)
from django.conf import settings
from rest_framework import exceptions

logger = logging.getLogger(__name__)
encryption = EncryptionMixin()


class VerifyOTPView(generics.CreateAPIView):
    permission_classes = ()
    authentication_classes = ()
    serializer_class = ConfirmSerializers

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        encrypted_password = serializer.validated_data.get("password")
        password = (
            encryption.decrypt_value(encrypted_password) if encrypted_password else None
        )

        confirm_key = serializer.validated_data["confirm_key"]
        otp_encrypted = serializer.validated_data["otp_encrypted"]

        try:
            if confirm_key:
                confirmation = TotpMailConfirmation.objects.select_related("user").get(
                    confirm_key=confirm_key
                )
                if confirmation._otp_expiry():
                    raise ExpiredException(
                        "Email confirmation expired, Please request a new one."
                    )

                is_otp_encryption = Configs._bool_setting(
                    "PASSWORD_ENCRYPTION", confirmation.company_id
                )
                raw_otp = (
                    _decrypted_password(otp_encrypted)
                    if is_otp_encryption
                    else otp_encrypted
                )
                if not check_password(raw_otp, confirmation.otp_encryption):
                    confirmation._failed_confirm()
                    # verify OPT attempt limit to prevent attacker from using bot to guess OTP automatically
                    otp_verify_attempt_limit = Configs._int_setting(
                        "OTP_VERIFY_ATTEMPT_LIMIT", confirmation.company_id
                    )
                    if confirmation.failed_confirm >= otp_verify_attempt_limit:
                        confirmation.clean()
                        raise BadRequestException(
                            "OPT verify reach attempt limit, Please request a new one."
                        )
                    raise BadRequestException(
                        "You enter an invalid code. Please try again!"
                    )

                user = confirmation.user
                user.otp_sent_count = 0
                confirmation.confirmed_at = timezone.now()
                confirmation.save(update_fields=("confirmed_at",))
                confirmation.clean()
                if user.state == "pending_verify_otp" or user.login_type == "social" or user.is_pending_verification:
                    from apps.auth_oauth.utils.token import issue_token_to_user
                    if user.is_required_reset_pwd and password:
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
                            raise exceptions.ValidationError({"detail": "Failed"})
                        user.login_type = "pwd"
                        user.is_required_reset_pwd = False
                        user.set_password(password)
                    # todo uncomment if web is goes the same flow
                    # else:
                    #     raise BadRequestException(
                    #         "Failed."
                    #     )
                    user.is_pending_verification = False
                    user.save(update_fields=("otp_sent_count", "is_pending_verification","login_type", "is_required_reset_pwd", "password",))
                    return issue_token_to_user(request, user, True)
                # Success response verify otp
                reset_token = generate_single_use_token(user.id)
                user.save(update_fields=("otp_sent_count",))
                return Response(
                    {"status": "otp_verified", "reset_token": reset_token, "message": "OTP verified successfully."},
                    status=status.HTTP_200_OK
                )
            else:
                return Response("Bad Request", status=status.HTTP_400_BAD_REQUEST)

        except serializers.ValidationError:
            raise BadRequestException("You enter an invalid code. Please try again!")
        except TotpMailConfirmation.DoesNotExist:
            raise NotFoundException("OTP dose not existed.")


class PasswordPreChangeVerifyOTPView(generics.CreateAPIView):
    permission_classes = ()
    authentication_classes = ()
    serializer_class = ConfirmSerializers

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        confirm_key = serializer.validated_data["confirm_key"]
        otp_encrypted = serializer.validated_data["otp_encrypted"]

        try:
            if confirm_key:
                confirmation = TotpMailConfirmation.objects.select_related("user").get(
                    confirm_key=confirm_key
                )
                if confirmation._otp_expiry():
                    raise ExpiredException(
                        "Email confirmation expired, Please request a new one."
                    )

                is_otp_encryption = Configs._bool_setting(
                    "PASSWORD_ENCRYPTION", confirmation.company_id
                )
                raw_otp = (
                    _decrypted_password(otp_encrypted)
                    if is_otp_encryption
                    else otp_encrypted
                )
                if not check_password(raw_otp, confirmation.otp_encryption):
                    confirmation._failed_confirm()
                    # verify OPT attempt limit to prevent attacker from using bot to guess OTP automatically
                    otp_verify_attempt_limit = Configs._int_setting(
                        "OTP_VERIFY_ATTEMPT_LIMIT", confirmation.company_id
                    )
                    if confirmation.failed_confirm >= otp_verify_attempt_limit:
                        confirmation.clean()
                        raise BadRequestException(
                            "OPT verify reach attempt limit, Please request a new one."
                        )
                    raise BadRequestException(
                        "You enter an invalid code. Please try again!"
                    )
                # *** issue token by auth_oauth utils function
                user = confirmation.user
                confirmation.confirmed_at = timezone.now()
                confirmation.save(update_fields=("confirmed_at",))
                if user.state == "pending_verify_otp":
                    confirmation.clean()
                    from apps.auth_oauth.utils.token import issue_token_to_user
                    return issue_token_to_user(request, user, True)
                    # Success response
                return Response(
                    {"status": "otp_verified", "message": "OTP verified successfully."},
                    status=status.HTTP_200_OK
                )
            else:
                return Response("Bad Request", status=status.HTTP_400_BAD_REQUEST)

        except serializers.ValidationError:
            raise BadRequestException("You enter an invalid code. Please try again!")
        except TotpMailConfirmation.DoesNotExist:
            raise NotFoundException("OTP dose not existed.")


class VerifyOTPResetPasswordView(VerifyOTPView):
    pass


class ResendView(generics.CreateAPIView):
    permission_classes = ()
    authentication_classes = ()
    serializer_class = ResendSerializers

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        confirm_key = serializer.validated_data["confirm_key"]

        try:
            result = TotpResendService.resend_otp(request, confirm_key)
            return Response(result, status=status.HTTP_200_OK)
        except TotpResendService.NotFoundException as e:
            logger.error(f"TotpResendService.NotFoundException: {str(e)}")
            raise serializers.ValidationError({"detail": "Unable to resend OTP"})
        except BadRequestException as e:
            logger.error(f"BadRequestException: {str(e)}")
            raise serializers.ValidationError({
                "detail": f"Reached the maximum resend limit ({LIMIT_RESEND_OTP})."
            })
        except Exception as e:
            logger.exception(f"Unexpected error during OTP resend: {e}")
            raise serializers.ValidationError({"detail": "Unable to resend OTP"})


class LoginResendOtpView(generics.CreateAPIView):
    permission_classes = ()
    authentication_classes = ()
    serializer_class = LoginResendSerializers

    def post(self, request, *args, **kwargs):

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"]

        user_query = User.objects.filter(
            username=username,
            status=UserStatus.ACTIVE,
            state=UserState.PENDING_VERIFY_OPT,
        )
        user = user_query.first()
        if not user:
            raise BadRequestException(
                f"Not found user :{username} in pending state OPT."
            )
        if user.otp_sent_count == LIMIT_RESEND_OTP:
            raise BadRequestException(
                f"Reach limit number({LIMIT_RESEND_OTP}) resend otp."
            )
        top_mail = EmailManager.issue_email_otp(user, request)
        user_query.update(otp_sent_count=F("otp_sent_count") + Value(1))
        return Response(
            data={
                "email": mask_email(user.email),
                "status": "confirm_otp",
                "message": "Please confirm your OTP to continue.",
                "token": top_mail.confirm_key,
                "retry_in": commons.retry_in_to_timestamp(top_mail.company_id),
                "expire_in": top_mail.otp_expiry,
            },
            status=status.HTTP_200_OK,
        )


class MailTemplateViewSet(AdminRecruiterOrRecruiterBaseViewSet):
    serializer_class = MailTemplateReadSerializer
    filterset_class = MailTemplateFilter
    ordering_fields = ["id", "create_date", "write_date"]
    ordering = ["-id"]
    search_fields = [
        "title",
        "subject",
    ]

    permission_codename = [
        "admin_recruiter_manage_job_post",
        "recruiter_manage_job_post",
    ]
    queryset = MailTemplate.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset()

        is_active = self.request.query_params.get("is_active")

        # Default filter only when missing or empty
        if is_active in [None, ""]:
            queryset = queryset.filter(is_active=True)
        # Explicit false
        if str(is_active).lower() == "false":
            return queryset.filter(is_active=False)
        # Explicit true
        if str(is_active).lower() == "true":
            return queryset.filter(is_active=True)
        
        return queryset
