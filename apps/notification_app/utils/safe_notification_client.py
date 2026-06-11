import logging

from wdg_notification.client import NotificationClient
from wdg_notification.exceptions import APIError

loggers = logging.getLogger(__name__)


class SafeNotificationClientUtil(NotificationClient):
    def _request(self, method, endpoint, **kwargs):
        url = f"{self.base_url}{endpoint}"
        response = self.session.request(method, url, **kwargs)
        if not response.ok:
            try:
                error_data = response.json()
            except ValueError:
                error_data = response.text[:500] or "No response body"
            raise APIError(response.status_code, error_data)

        # Handling empty response
        if not response.text.strip():
            return {"status": "success", "message": "No response body"}

        # Handling non-JSON response
        try:
            return response.json()
        except ValueError:
            loggers.error(
                f"[SafeNotificationClientUtil] Non-JSON response received from {url}: {response.text[:200]}"
            )
            return {"status": "success", "message": response.text[:200]}
