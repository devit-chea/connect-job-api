from django.conf import settings
from apps.base.services.external_api_client_service import ExternalAPIClient
from apps.auth_oauth.constants.content_type_constants import FileContentType


class CVTokenService:
    CV_SCAN_BASIC_TOKEN = getattr(settings, "CV_SCAN_BASIC_TOKEN", None)
    CV_SCAN_GET_TOKEN_URL = getattr(settings, "CV_SCAN_GET_TOKEN_URL", None)

    @classmethod
    def get_access_token(cls):
        client = ExternalAPIClient(
            base_url=cls.CV_SCAN_GET_TOKEN_URL,
        )
        payload = {
            "grant_type": "client_credentials",
        }
        return client.post(
            "/oauth2/token",
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": cls.CV_SCAN_BASIC_TOKEN
            },
        )


class CVExtractService:
    CV_SCAN_URL = getattr(settings, "CV_SCAN_URL", None)

    @classmethod
    def extract(cls, payload, content_type=FileContentType.BASE64):
        token = CVTokenService.get_access_token()

        client = ExternalAPIClient(
            base_url=cls.CV_SCAN_URL,
            api_key=token["access_token"],
        )
        
        CV_EXTRACT_ENDPOINT = "/webhook/cv/extract/"
        if content_type == FileContentType.FILE:
            return client.post(CV_EXTRACT_ENDPOINT, files=payload)
        return client.post_json(CV_EXTRACT_ENDPOINT, payload=payload)
        
