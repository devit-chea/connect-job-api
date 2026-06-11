import logging

from celery import shared_task
from django.core.mail import send_mail
from wdg_notification.exceptions import APIError

from apps.notification_app.utils.notification import NotificationClientUtil

logger = logging.getLogger(__name__)


@shared_task(
    name="notification_task.send_confirmation_email_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def send_confirmation_email_task(self, subject, body, email_from, recipient):
    try:
        send_mail(
            subject=subject,
            message="",  # fallback text if HTML not supported
            from_email=email_from,
            recipient_list=[recipient],
            html_message=body,
            fail_silently=False,
        )
        logger.info(f"Confirmation email sent to {recipient}")
    except Exception as exc:
        logger.exception(f"Failed to send confirmation email to {recipient}")
        raise self.retry(exc=exc)


@shared_task(
    name="notification_task.send_notification_email_via_service_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def send_notification_email_via_service_task(self, email_data: dict) -> None:
    try:
        logger.info("[Notification Task] Sending notification...")
        NotificationClientUtil.send_notification(email_data)
        logger.info("[Notification Task] Finished sending notification.")
    except APIError as e:
        logger.error(f"[Notification Task] APIError: status={e.status_code}, body={e}")
        raise self.retry(exc=e)
    except Exception as exc:
        logger.exception("[Notification Task] Notification service failed, retrying...")
        raise self.retry(exc=exc)
