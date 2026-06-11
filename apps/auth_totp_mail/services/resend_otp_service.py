import logging

from django.db import transaction
from django.db.models import Value, F
from rest_framework import serializers

from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.services.telegram_otp_service import send_otp_via_telegram
from apps.auth_totp_mail.models.mail_template_models import TotpMailConfirmation
from apps.auth_totp_mail.utils import commons
from apps.auth_totp_mail.utils.email import mask_email
from apps.core.exceptions.base_exceptions import BadRequestException
from config.settings.base import LIMIT_RESEND_OTP

logger = logging.getLogger(__name__)


class TotpResendService:
    class NotFoundException(Exception):
        pass

    @staticmethod
    def resend_otp(request, confirm_key):
        try:
            with transaction.atomic():
                totp_mail = (
                    TotpMailConfirmation.objects
                    .select_related("user")
                    .select_for_update()
                    .get(confirm_key=confirm_key)
                )
        except TotpMailConfirmation.DoesNotExist:
            raise serializers.ValidationError({"detail": "Unable to resend OTP"})

        user = totp_mail.user
        if user.otp_sent_count >= LIMIT_RESEND_OTP:
            raise BadRequestException(
                f"Reach limit number({LIMIT_RESEND_OTP}) resend otp."
            )

        otp_instance = commons.generate_otp_instance(request)
        new_confirmation_key = commons.generate_key_confirm()

        totp_mail.send_at = commons.timezone.now()
        totp_mail.confirm_key = new_confirmation_key
        totp_mail.otp_expiry = otp_instance.otp_expiry
        totp_mail.otp_encryption = otp_instance.otp_encrypted
        totp_mail.save(update_fields=[
            "send_at", "confirm_key", "otp_expiry", "otp_encryption"
        ])
        User.objects.filter(pk=user.pk).update(
            otp_sent_count=F("otp_sent_count") + Value(1)
        )
        # telegram
        if user.login_type == "telegram" and user.telegram_chat_id:
            send_otp_via_telegram(user.telegram_chat_id, otp_instance.otp)
            logger.info(f"Resent Telegram link to user_id={user.id}")
            return {
                "status": "confirm_otp",
                "message": "Please confirm your OTP to continue.",
                "token": new_confirmation_key,
                "retry_in": commons.retry_in_to_timestamp(totp_mail.company_id),
                "expire_in": totp_mail.otp_expiry,
            }

        template_context = commons.template_context(request, totp_mail, otp_instance.otp)
        totp_mail.send(template_context)
        logger.info(f"Resent OTP to {totp_mail.email}, user_id={user.id}")
        return {
            "email": mask_email(user.email),
            "status": "confirm_otp",
            "message": "Please confirm your OTP to continue.",
            "token": new_confirmation_key,
            "retry_in": commons.retry_in_to_timestamp(totp_mail.company_id),
            "expire_in": totp_mail.otp_expiry,
            "employee_info": {
                "full_name": f"{user.first_name} {user.last_name}",
                "email": totp_mail.email
            }
        }
