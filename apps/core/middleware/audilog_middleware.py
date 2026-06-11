from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest

from auditlog.middleware import AuditlogMiddleware
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from apps.auth_oauth.authentication import CustomJWTAuthentication


class JWTAuditlogMiddleware(AuditlogMiddleware):
    """
    Custom Auditlog middleware that populates request.user from JWT
    before auditlog sets the actor.
    """

    def _authenticate_jwt(self, request: HttpRequest):
        """Return authenticated user from JWT, or AnonymousUser"""
        auth = CustomJWTAuthentication()
        header = auth.get_header(request)
        if not header:
            return AnonymousUser()

        raw_token = auth.get_raw_token(header)
        if not raw_token:
            return AnonymousUser()

        try:
            validated_token = auth.get_validated_token(raw_token)
            return auth.get_user(validated_token)
        except (InvalidToken, TokenError):
            return AnonymousUser()

    def __call__(self, request):
        # Only populate user if not already authenticated
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            request.user = self._authenticate_jwt(request)

        # Let AuditlogMiddleware do its normal work
        return super().__call__(request)
