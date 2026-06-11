from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from typing import Optional


def get_ucp_by_id(ucp_id: int) -> Optional[UserCompanyProfile]:
    """
    Retrieves a UserCompanyProfile instance by its primary key (ID).

    Uses select_related to efficiently fetch the associated 'profile'
    in the same query to avoid N+1 issues when accessing the profile later.
    """
    ucp = UserCompanyProfile.objects.select_related("profile").filter(pk=ucp_id).first()
    return ucp
