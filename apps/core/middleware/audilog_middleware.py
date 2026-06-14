from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest

from auditlog.middleware import AuditlogMiddleware
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from apps.auth_oauth.authentication import CustomJWTAuthentication


class JWTAuditlogMiddleware(AuditlogMiddleware):
    """
    Custom Auditlog middleware that populates request.user from JWT
    before auditlog sets the actor.
    """

    def _authenticate_jwt(self, request: HttpRequest):
        """
        Resolve the JWT actor for audit logging.

        Uses JWTAuthentication (base class) for token validation so the Redis
        JTI revocation check is skipped here — it runs again in the DRF view
        layer via CustomJWTAuthentication. Skipping it in this middleware saves
        one Redis round-trip per request.
        """
        custom_auth = CustomJWTAuthentication()
        header = custom_auth.get_header(request)
        if not header:
            return AnonymousUser()

        raw_token = custom_auth.get_raw_token(header)
        if not raw_token:
            return AnonymousUser()

        try:
            # Signature + expiry check only — no Redis JTI lookup
            base_auth = JWTAuthentication()
            validated_token = base_auth.get_validated_token(raw_token)
            return custom_auth.get_user(validated_token)
        except (InvalidToken, TokenError):
            return AnonymousUser()

    def __call__(self, request):
        # Only populate user if not already authenticated
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            request.user = self._authenticate_jwt(request)

        # Let AuditlogMiddleware do its normal work
        return super().__call__(request)
