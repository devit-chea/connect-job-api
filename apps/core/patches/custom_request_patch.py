from rest_framework.views import APIView
from apps.core.middleware.requests import CustomJWTRequest

_original_initialize_request = APIView.initialize_request

def custom_initialize_request(self, request, *args, **kwargs):
    raw_request = _original_initialize_request(self, request, *args, **kwargs)
    return CustomJWTRequest(
        raw_request._request,
        parsers=self.get_parsers(),
        authenticators=self.get_authenticators(),
        negotiator=self.get_content_negotiator(),
        parser_context=self.get_parser_context(raw_request),
    )

APIView.initialize_request = custom_initialize_request