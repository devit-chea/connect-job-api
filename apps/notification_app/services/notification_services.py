import logging

from django.apps import apps as django_apps
from django.conf import settings
from django.template import engines
from django.template.loader import render_to_string

from apps.base.utils.settings_util import get_web_base_url
from apps.notification_app.tasks.tasks import send_notification_email_via_service_task
from apps.notification_app.utils.notification import (
    NotificationClientUtil,
    NotificationEmailTemplateBuilder,
)
from config.celery import app
from config.settings.base import API_BASE_URL

logger = logging.getLogger(__name__)


class NotificationServices:
    @staticmethod
    def send_email(
        instance,
        template_context: dict = None,
        subject_template_name_str: str = None,
        body_template_name_str: str = None,
    ):

        try:
            # Sender
            company_id = getattr(instance, "company_id", None) or 1
            email_from = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com")

            # Receiver
            user_id = template_context.get("user_id")
            recipient = template_context.get("recipient")
            if not user_id or not email_from:
                raise ValueError("User id and recipient's email are required.")

            # Subject and body
            subject = (
                render_to_string(subject_template_name_str, template_context)
                .strip()
                .replace("\n", "")
            )
            body = render_to_string(body_template_name_str, template_context)

            if settings.WDG_NOTIFICATION_IS_ENABLE:
                email_data = NotificationEmailTemplateBuilder(
                    receiver_id=user_id,
                    receiver_email=recipient,
                    sender_id=company_id,
                    sender_email=email_from,
                    subject=subject,
                    content=body,
                ).build()
                try:
                    result = NotificationClientUtil.send_notification(email_data)
                except Exception:
                    logger.info("Email send failed fallback to celery retry")
                    result = send_notification_email_via_service_task.delay(email_data)

            else:
                args = [subject, body, email_from, recipient, company_id]
                result = app.send_task("apps.base.tasks.tasks.send_email", args=args)

            logger.info(f"Email send task dispatched: task_id={result}")
            return result  # caller can check task status using this result
        except Exception as exc:
            logger.exception("Failed to send email to")
            raise exc

    @staticmethod
    def send_email_from_db_template(
        instance,
        *,
        template_id: int,
        template_context: dict,
        metadata=None,
        is_system=False,
        from_email=None,
        to_email=None,
        is_in_app=True,
        is_popup=False,
        force_send=False,
        direct_push=False,
        company=None,
        recipients=None,
        send_type=None,
        channels: list[str] = None,
        **kwargs,
    ):
        """
        Render subject/body from MailTemplate (DB) and dispatch email
        Required in template_context: user_id (receiver), recipient (email).
        """
        try:
            from apps.auth_oauth.models.auth_models import User

            # sys_setting = get_sys_setting(company)

            # Sender
            company_id = getattr(instance, "company_id", None) or 1
            email_from = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com")
            MailTemplate = django_apps.get_model("auth_totp_mail", "MailTemplate")

            # Receiver
            user_id = template_context.get("user_id")
            recipient = template_context.get("recipient")
            if not user_id or not recipient:
                raise ValueError(
                    "user_id and recipient are required in template_context."
                )

            # Load & render DB template
            get_mail_template = MailTemplate.objects.get(pk=template_id)
            template_engines = engines["django"]
            subject = (
                template_engines.from_string(get_mail_template.subject)
                .render(template_context)
                .strip()
                .replace("\n", "")
            )
            body = template_engines.from_string(get_mail_template.body).render(
                template_context
            )

            # sender
            sender = User.objects.filter(email=from_email).first()
            sender = sender or User.objects.filter(is_superuser=True).first()
            metadata = (
                {}
                if metadata is None
                else NotificationClientUtil().to_dict_data(metadata)
            )
            metadata.update(
                {
                    **kwargs,
                    "company_id": str(company_id),
                    "sender_data": NotificationServices.get_sender(
                        sender, email_from, email_from, is_system
                    ),
                    "mail_header": None,  # TODO: Mail header
                    "api_base_url": API_BASE_URL,
                    "web_base_url": get_web_base_url(),
                    "extra": {},
                    "send_type": send_type,
                }
            )

            # Receiver
            receiver = User.objects.filter(email=recipient).first()

            receiver_data = {
                "receiver_data": {
                    "id": str(getattr(receiver, "id", "")),
                    "email": getattr(receiver, "email", None),
                    "username": getattr(receiver, "username", None),
                    "first_name": getattr(receiver, "first_name", None),
                    "last_name": getattr(receiver, "last_name", None),
                    "full_name": f"{getattr(receiver, 'first_name', '')} {getattr(receiver, 'last_name', '')}".strip(),
                },
            }

            metadata.update(receiver_data)

            # To check if the WDG Notification enabled.
            if settings.WDG_NOTIFICATION_IS_ENABLE:
                email_data = NotificationEmailTemplateBuilder(
                    receiver_id=user_id,
                    receiver_email=recipient,
                    sender_id=company_id,
                    sender_email=email_from,
                    subject=subject,
                    content=body,
                    metadata=metadata,
                ).build()

                result = NotificationClientUtil.send_notification(email_data)
            else:
                args = [subject, body, email_from, recipient, company_id]
                result = app.send_task("apps.base.tasks.tasks.send_email", args=args)

            logger.info(
                f"[DBTemplate] Email task dispatched: template_id={template_id}"
            )
            return result
        except Exception as exc:
            logger.error(exc)
            logger.exception("[DBTemplate] Failed to send email")
            raise


    @staticmethod
    def send_email_from_db_template_v1(
        instance,
        *,
        template_id: int,
        template_context: dict,
    ):
        """
        Render subject/body from MailTemplate (DB) and dispatch email
        Required in template_context: user_id (receiver), recipient (email).
        """
        try:
            # Sender
            company_id = getattr(instance, "company_id", None) or 1
            email_from = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com")
            MailTemplate = django_apps.get_model("auth_totp_mail", "MailTemplate")
            # Receiver
            user_id = template_context.get("user_id")
            recipient = template_context.get("recipient")
            if not user_id or not recipient:
                raise ValueError(
                    "user_id and recipient are required in template_context."
                )

            # Load & render DB template
            get_mail_template = MailTemplate.objects.get(pk=template_id)
            template_engines = engines["django"]
            subject = (
                template_engines.from_string(get_mail_template.subject)
                .render(template_context)
                .strip()
                .replace("\n", "")
            )
            body = template_engines.from_string(get_mail_template.body).render(
                template_context
            )

            if settings.WDG_NOTIFICATION_IS_ENABLE:
                email_data = NotificationEmailTemplateBuilder(
                    receiver_id=user_id,
                    receiver_email=recipient,
                    sender_id=company_id,
                    sender_email=email_from,
                    subject=subject,
                    content=body,
                ).build()
                try:
                    result = NotificationClientUtil.send_notification(email_data)
                    logger.info(
                        f"[DBTemplate] Email sent directly: template_id={template_id}"
                    )
                except Exception:
                    logger.info(
                        "[DBTemplate] Direct send failed, falling back to Celery"
                    )
                    try:
                        result = send_notification_email_via_service_task.delay(
                            email_data
                        )
                    except Exception as celery_err:
                        logger.warning(
                            f"[DBTemplate] Celery fallback also failed: {celery_err}"
                        )
                        result = None
            else:
                try:
                    args = [subject, body, email_from, recipient, company_id]
                    result = app.send_task(
                        "apps.base.tasks.tasks.send_email", args=args
                    )
                except Exception as celery_err:
                    logger.warning(
                        f"[DBTemplate] Email task dispatch failed: {celery_err}"
                    )
                    result = None

            logger.info(
                f"[DBTemplate] Email dispatched: template_id={template_id}, task_id={result}"
            )
            return result
        except Exception as exc:
            logger.exception("[DBTemplate] Failed to send email")
            raise
        

    def get_sender(sender, mail_from, sys_mail_from, is_system):
        return {
            "id": str(getattr(sender, "id", "")),
            "email": mail_from,
            "email_address": sys_mail_from,
            "username": getattr(sender, "username", None),
            "first_name": getattr(sender, "first_name", None),
            "last_name": getattr(sender, "last_name", None),
            "full_name": f"{getattr(sender, 'first_name', '')} {getattr(sender, 'last_name', '')}".strip(),
        }
