from rest_framework import status
from rest_framework.response import Response

from apps.auth_totp_mail.models.mail_template_models import EmailManager
from .commons import retry_in_to_timestamp


def mask_email(email: str) -> str:
    if "@" not in email:
        return email
    name, domain = email.split("@", 1)
    show = 2
    if len(name) <= show:
        masked = name[0] + "*"
    else:
        masked = name[:show] + "*" * (len(name) - show)
    return f"{masked}@{domain}"


# check user confirm email session | return bool
def is_required_email_confirm_login(request, user):

    totp_mail = EmailManager.issue_email_otp(user, request)
    return Response(
        data={
            "email": mask_email(user.email),
            "status": "confirm_otp",
            "message": "Please confirm your OTP to continue.",
            "token": totp_mail.confirm_key,
            "retry_in": retry_in_to_timestamp(totp_mail.company_id),
            "expire_in": totp_mail.otp_expiry,
        },
        status=status.HTTP_200_OK
    )