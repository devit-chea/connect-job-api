import logging

from rest_framework import status
from rest_framework.response import Response

from .commons import retry_in_to_timestamp
from ..models.mail_template_models import EmailManager
from ...auth_oauth.services.telegram_otp_service import send_otp_via_telegram


logger = logging.getLogger(__name__)
def is_required_telegram_confirm_login(request, user):

    totp, otp = EmailManager.issue_telegram_otp(user, request)

    sent = send_otp_via_telegram(user.telegram_chat_id, otp)
    logger.info(f"Sent otp status:::: {sent}")
    return Response(
        data={
            "status": "confirm_otp",
            "message": "Please confirm your OTP to continue.",
            "token": totp.confirm_key,
            "retry_in": retry_in_to_timestamp(totp.company_id),
            "expire_in": totp.otp_expiry,
        },
        status=status.HTTP_200_OK
    )
