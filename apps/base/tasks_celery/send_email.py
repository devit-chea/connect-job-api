from __future__ import absolute_import, unicode_literals

from django.core.mail import send_mail
from apps.base.utils.settings_util import (
    Settings,
    CONST_DEFAULT_FROM_EMAIL,
    CONST_ENABLE_REAL_EMAIL,
    CONST_DEFAULT_TO_EMAIL
)
from email.utils import formataddr


def send_email(title, body, from_email, to_emails, company_id, html_message=None):
    default_from_email = Settings.get_system_setting(CONST_DEFAULT_FROM_EMAIL, company_id)
    from_email, to_emails = check_email(from_email, to_emails, company_id)
    formatted_sender = formataddr((from_email, default_from_email))
    send_mail(
        subject=title,
        message=body,
        html_message=html_message,
        from_email=formatted_sender,
        recipient_list=to_emails,
    )


def check_email(from_email, to_emails, company_id):
    default_to_email = Settings.get_system_setting(CONST_DEFAULT_TO_EMAIL, company_id)
    default_from_email = Settings.get_system_setting(CONST_DEFAULT_FROM_EMAIL, company_id)
    is_enable_real_email = Settings.get_system_setting(CONST_ENABLE_REAL_EMAIL, company_id)
    from_email = from_email or default_from_email

    if isinstance(to_emails, str):
        to_emails = [to_emails]

    to_emails = (
        to_emails
        if to_emails and is_enable_real_email
        else [default_to_email]
    )

    return from_email, to_emails
