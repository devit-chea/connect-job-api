import json
import logging
from typing import Optional
from django.conf import settings
from wdg_notification.utils import Utils

from wdg_notification.client import NotificationClient

from apps.notification_app.utils.safe_notification_client import (
    SafeNotificationClientUtil,
)

client = SafeNotificationClientUtil(
    base_url=settings.WDG_NOTIFICATION_BASE_URL,
    app_id=settings.WDG_NOTIFICATION_APP_ID,
    secret_key=settings.WDG_NOTIFICATION_SECRET_KEY,
)


class APIError(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message
        super().__init__(f"APIError {status_code}: {message}")


loggers = logging.getLogger(__name__)


class NotificationClientUtil:

    def __init__(self, base_url=None, app_id=None, secret_key=None):
        self.base_url = settings.WDG_NOTIFICATION_BASE_URL
        self.client = NotificationClient(
            base_url=base_url or settings.WDG_NOTIFICATION_BASE_URL,
            app_id=app_id or settings.WDG_NOTIFICATION_APP_ID,
            secret_key=secret_key or settings.WDG_NOTIFICATION_SECRET_KEY,
        )

    def connect(self):
        return NotificationClient(
            base_url=self.base_url,
            app_id=settings.WDG_NOTIFICATION_APP_ID,
            secret_key=settings.WDG_NOTIFICATION_SECRET_KEY,
            timeout=settings.WDG_NOTIFICATION_TIMEOUT,
        )

    # Send notification email
    @staticmethod
    def send_notification(data):
        response = None
        try:
            response = client.send_notification(data)
            return response.json() if hasattr(response, "json") else response
        except APIError as e:
            loggers.error(f"Notification APIError: {e}")
            raise
        except ValueError:
            # non-JSON fallback
            loggers.error(
                f"Notification returned non-JSON response: {response.text[:500]}"
            )
            return {"status": "success", "message": response.text[:500]}

    def get_notifications(self, query_params=None):
        """
        Fetch notifications from Notification Service.

        :param query_params: dict (optional)
            Example:
            {
                "page": 1,
                "page_size": 10,
                "is_read": False,
                receiver_id: 1,
                metadata__key: value,
                metadata__key__key: value
            }
        :return: dict / response from service
        """
        try:
            response = self.client.get_notifications(query_params=query_params or {})
            return response
        except Exception as e:
            # You can replace this with structured logging
            loggers.error(f"Failed to fetch notifications: {e}")
            raise

    def get_notification(self, notification_id, query_params=None):
        """
        Get a single notification by ID
        """
        if not notification_id:
            raise ValueError("notification_id is required")

        try:
            return self.client.get_notification(
                notification_id=notification_id, query_params=query_params or {}
            )
        except Exception:
            loggers.error(
                f"Failed to fetch notification {notification_id}", exc_info=True
            )
            raise

    def get_unread_count(self, query_params=None):
        """
        Get total unread notifications count
        """
        try:
            return self.client.get_unread_count(query_params=query_params or {})
        except Exception:
            loggers.error("Failed to get unread count", exc_info=True)
            raise

    def mark_as_read(self, notification_id, query_params=None):
        """
        Mark a single notification as read
        """
        if not notification_id:
            raise ValueError("notification_id is required")

        try:
            return self.client.mark_as_read(
                notification_id=notification_id, query_params=query_params or {}
            )
        except Exception:
            loggers.error(
                f"Failed to mark notification {notification_id} as read", exc_info=True
            )
            raise

    def mark_all_read(self, query_params=None):
        """
        Mark all notifications as read
        """
        try:
            return self.client.mark_all_read(query_params=query_params or {})
        except Exception:
            loggers.error("Failed to mark all notifications as read", exc_info=True)
            raise

    def query_params_util(self, query_params):
        return Utils.query_params(query_params)

    def to_dict_data(self, metadata):
        if isinstance(metadata, dict):
            metadata = {
                key: str(value) if not isinstance(value, (str, dict, list)) else value
                for key, value in metadata.items()
            }

        elif isinstance(metadata, list):
            metadata = [
                {
                    key: (
                        str(value)
                        if not isinstance(value, (str, dict, list))
                        else value
                    )
                    for key, value in item.items()
                }
                for item in metadata
            ]

        elif isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                logging.error(
                    "Notification Service - Error decoding JSON string: {}".format(
                        metadata
                    )
                )
                metadata = {}
        else:
            metadata = {}

        return metadata


class NotificationEmailTemplateBuilder:
    """
    Build notification email template
    :param receiver_id: optional[str]
    :param receiver_email: required[str]
    :param subject: required[str]
    :param content: required[str]
    :param sender_id: Optional[str]
    :param sender_email: Optional[str]
    :param is_in_app: Optional[bool]
    :param is_system: Optional[bool]
    :param metadata: Optional[dict]
    """

    def __init__(
        self,
        receiver_id: str,
        receiver_email: str,
        subject: str,
        content: str,
        sender_id: Optional[str] = "1",
        sender_email: Optional[str] = settings.WDG_NOTIFICATION_EMAIL,
        is_in_app: Optional[bool] = True,
        is_system: Optional[bool] = True,
        metadata: Optional[dict] = None,
    ):
        if metadata is None:
            metadata = {}
        if not receiver_email or not subject or not content:
            raise ValueError("Receiver email, subject and content are required.")
        self.receiver_id = receiver_id
        self.receiver_email = receiver_email
        self.subject = subject
        self.content = content
        self.sender_id = sender_id
        self.sender_email = sender_email
        self.is_in_app = is_in_app
        self.is_system = is_system
        self.metadata = metadata

    def build(self):
        return {
            "receivers": [
                {
                    "receiver_id": self.receiver_id,
                    "email": self.receiver_email,
                    "metadata": self.metadata or {},
                }
            ],
            "sender": {
                "id": self.sender_id,
                "email": self.sender_email,
                "email_address": self.sender_email,
            },
            "channels": ["email"],
            "is_in_app": self.is_in_app,
            "is_system": self.is_system,
            "title": self.subject,
            "content": self.content,
            "metadata": self.metadata or {},
        }
