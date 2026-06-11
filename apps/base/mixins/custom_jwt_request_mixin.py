from apps.core.middleware.requests import CustomJWTRequest


class CustomJWTRequestMixin:
    def initialize_request(self, request, *args, **kwargs):
        raw_request = super().initialize_request(request, *args, **kwargs)
        return CustomJWTRequest(
            raw_request._request,
            parsers=self.get_parsers(),
            authenticators=self.get_authenticators(),
            negotiator=self.get_content_negotiator(),
            parser_context=self.get_parser_context(raw_request),
        )
