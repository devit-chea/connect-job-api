import json
import logging
import requests
from requests.exceptions import RequestException, Timeout


logger = logging.getLogger(__name__)


class ExternalAPIClient:
    """
    Reusable HTTP client for calling external services.
    Handles timeouts, connection errors, and robust JSON parsing.
    """

    def __init__(self, base_url: str, api_key: str = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    # ------------------------------
    # Internal helpers
    # ------------------------------

    def _headers(self, extra=None, json_request=False):
        headers = {}

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        if json_request:
            headers.setdefault("Content-Type", "application/json")
            headers.setdefault("Accept", "application/json")


        if extra:
            headers.update(extra)

        return headers

    def _request(self, method: str, path: str, timeout: int, **kwargs):
        """
        Internal reusable HTTP handler for GET, POST, PUT, DELETE...
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = self._headers(kwargs.pop("headers", None))

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=timeout,
                **kwargs,
            )
        except Timeout as e:
            logger.error(f"API Timeout: {e}")
            raise Exception(
                f"External API Timeout Error: Request to {url} exceeded {timeout} seconds."
            ) from e
        except RequestException as e:
            logger.error(f"API Connection: {e}")
            raise Exception(
                f"External API Connection Error: Failed to connect to {url}."
            ) from e
        except Exception as e: 
            logger.error(f"API Exception: {e}")
            raise Exception(
                f"External API Exception Error: Failed to connect to {url}."
            ) from e
            
        # HTTP error handling
        if not response.ok:
            raise Exception(
                f"External API Error ({response.status_code}): {response.text}"
            )

        # No content
        if response.status_code == 204:
            return None

        # Try JSON parse
        try:
            return response.json()
        except json.JSONDecodeError as e:
            raise Exception(
                f"External API returned non-JSON content despite successful status "
                f"({response.status_code}). Raw content starts with: "
                f"{response.text}"
            ) from e

    # ------------------------------
    # Public request wrappers
    # ------------------------------

    def post(self, path: str, data=None, files=None, headers=None, timeout=60):
        return self._request(
            "POST", path, timeout, data=data, files=files, headers=headers
        )

    def get(self, path: str, params=None, headers=None, timeout=60):
        return self._request(
            "GET", path, timeout, params=params, headers=headers
        )

    def post_json(self, path: str, payload: dict, timeout=60):
        return self._request(
            "POST",
            path,
            timeout,
            json=payload,
            headers=self._headers(json_request=True),
        )