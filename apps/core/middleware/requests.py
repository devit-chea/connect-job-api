import logging

from rest_framework.request import Request

logger = logging.getLogger(__name__)

class CustomJWTRequest(Request):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("CustomJWTRequest initialized")

    @property
    def jwt_claims(self):
        if hasattr(self.auth, "payload"):
            return self.auth.payload
        elif isinstance(self.auth, dict):
            return self.auth
        return {}

    @property
    def user_company_profile_id(self):
        return self.jwt_claims.get("user_company_profile_id")

    @property
    def user_id(self):
        return self.jwt_claims.get("user_id")

    @property
    def company_id(self):
        company_id = self.jwt_claims.get("company_id")
        if company_id:
            return company_id
        ucp_id = self.jwt_claims.get("user_company_profile_id")
        if ucp_id:
            try:
                from apps.auth_oauth.models.user_company_profile import (
                    UserCompanyProfile,
                )
                ucp = (
                    UserCompanyProfile.objects.select_related("company")
                    .filter(id=ucp_id, company__is_active=True)
                    .first()
                )
                if ucp and ucp.company_id:
                    return ucp.company_id
            except Exception:
                logger.warning("company_id DB fallback failed", exc_info=True)

        return None

    @property
    def user_type(self):
        return self.jwt_claims.get("type")

    @property
    def profile_id(self):
        return self.jwt_claims.get("profile_id")
