from django_elasticsearch_dsl_drf.viewsets import DocumentViewSet
from rest_framework.permissions import AllowAny

from apps.core.middleware.requests import CustomJWTRequest


class BaseDocumentViewSet(DocumentViewSet):
    def initialize_request(self, request, *args, **kwargs):
        raw_request = super().initialize_request(request, *args, **kwargs)
        return CustomJWTRequest(
            raw_request._request,
            parsers=self.get_parsers(),
            authenticators=self.get_authenticators(),
            negotiator=self.get_content_negotiator(),
            parser_context=self.get_parser_context(raw_request),
        )


class BasePublicDocumentViewSet(DocumentViewSet):
    permission_classes = [AllowAny]
