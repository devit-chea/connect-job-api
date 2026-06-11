from django.utils import timezone

from apps.notification_app.services.notification_services import NotificationServices
from config.settings import base as settings
from apps.auth_setting.config import Configs


class EmailService:

    def send_default_password(self, user, template_context=None):
        subject = "default_password/default_password_subject.txt"
        # remove unnecessary line breaks
        subject = "".join(subject.splitlines()).strip()
        body = "default_password/default_password_message.html"
        NotificationServices().send_email(user, template_context, subject, body)

    def send_invite(self, user, template_context=None):
        subject = "invite_user/invite_user_subject.txt"
        # remove unnecessary line breaks
        subject = "".join(subject.splitlines()).strip()
        body = "invite_user/invite_user_message.html"

        NotificationServices().send_email(user, template_context, subject, body)

    def template_context(self, user: object, default_password) -> dict:
        template_context = dict(Configs._setting("AUTH_TOTP_MAIL_TEMPLATE_CONTEXT"))
        template_context["default_password"] = default_password
        template_context["send_at"] = timezone.now()
        template_context["recipient"] = user.email
        template_context["username"] = user.username
        template_context["user_id"] = user.id
        template_context["first_name"] = user.first_name
        template_context["user_agent"] = None
        template_context["login_url"] = settings.WEB_BASE_URL_LOGIN
        template_context["contact_us_url"] = settings.WEB_BASE_URL_CONTACT_US
        return template_context
