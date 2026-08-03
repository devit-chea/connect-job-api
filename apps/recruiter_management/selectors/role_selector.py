from django.db.models import Q, QuerySet

from apps.auth_oauth.constants.auth_constants import UserTypes
from apps.auth_oauth.models.role_model import Role


def get_allowed_recruiter_roles(company_id, user_company_profile_id) -> QuerySet[Role]:
    """
    Roles an admin_recruiter (identified by their own user_company_profile_id)
    may assign when creating a "recruiter" user for their company.

    1. If the Operator has customized role(s) for this specific admin's UCP
       (Role.custom_for_ucp_id == user_company_profile_id), that is the
       exhaustive allowed set — company-wide defaults are not also included.
    2. Otherwise, fall back to the default recruiter role(s): type=recruiter,
       is_default=True, active=True, scoped to (this company OR public/global
       templates) — seeded default roles live on the platform's DEFAULT
       company with is_public=True, not on each tenant company, so a plain
       company_id filter alone would match nothing.
    """
    if user_company_profile_id:
        custom_qs = Role.objects.filter(
            custom_for_ucp_id=user_company_profile_id, active=True
        )
        if custom_qs.exists():
            return custom_qs

    if not company_id:
        return Role.objects.none()

    return Role.objects.filter(
        Q(company_id=company_id) | Q(is_public=True),
        type=UserTypes.RECRUITER.value,
        is_default=True,
        active=True,
    )
