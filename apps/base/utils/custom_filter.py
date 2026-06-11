from django.db.models import Q
from rest_framework.filters import BaseFilterBackend
from rest_framework.permissions import SAFE_METHODS
from apps.auth_oauth.constants.auth_constants import UserTypes

from apps.auth_oauth.utils.auth_util import get_active_profile_id


def effective_scope(request) -> str:
    from apps.auth_oauth.services.permission_service import PermissionService
    try:
        _, ctx = PermissionService().get_user_roles_and_permissions(request)
        roles = list(ctx.get("roles") or [])
        if not roles:
            return "OWN"
        return (
            "ALL"
            if any(getattr(r, "own_only", True) is False for r in roles)
            else "OWN"
        )
    except Exception:
        return "OWN"


class JobPostRecruiterScopeFilterBackend(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        if not request.user or not request.user.is_authenticated:
            return queryset.none()

        user_type = getattr(request, "user_type", None)
        company_id = getattr(request, "company_id", None)
        ucp_id = getattr(request, "user_company_profile_id", None)

        if user_type == UserTypes.SUPER_ADMIN.value:
            return queryset

        if not company_id:
            return queryset.none()

        if user_type == UserTypes.ADMIN_RECRUITER.value:
            return queryset.filter(company_id=company_id)

        if user_type == UserTypes.RECRUITER.value:
            scope = effective_scope(request)
            if scope == "ALL":
                return queryset.filter(company_id=company_id)

            owned_q = Q(company_id=company_id, create_ucp_id=str(ucp_id))
            assigned_q = Q(
                company_id=company_id,
                job_post_assigned_recruiters__assigned_ucp_id=str(ucp_id),
                job_post_assigned_recruiters__is_deleted=False,
            )
            return queryset.filter(owned_q | assigned_q).distinct()

        return queryset.none()


class CompanyOrUserProfileFilterBackend(BaseFilterBackend):
    """
    Filters queryset to include records where:
    (company_id == user's company_id)
    OR
    (create_uid == user_id AND create_ucp_id == user_company_profile_id)
    """

    def filter_queryset(self, request, queryset, view):

        # Step 1: Check authentication
        if not request.user or not request.user.is_authenticated:
            return queryset

        user_type = getattr(request, "user_type", None)
        if user_type == "super_admin":
            return queryset

        company_id = getattr(request, "company_id", None)
        user_id = getattr(request, "user_id", None)
        user_company_profile_id = getattr(request, "user_company_profile_id", None)

        # Build Q filters carefully (ignore None values)
        filters = Q()

        if user_type == UserTypes.ADMIN_RECRUITER.value:
            filters |= Q(company_id=company_id)

        if user_type == UserTypes.RECRUITER.value:
            filters |= Q(
                create_uid=user_id,
                create_ucp_id=user_company_profile_id,
                company_id=company_id,
            )

        return queryset.filter(filters)


class CompanyAndRoleScopeFilterBackend(BaseFilterBackend):
    """
    1) Company scope:
       - READ (SAFE methods): include same-company OR public (if model has `is_public`)
       - WRITE (non-SAFE):    restrict to same-company only
    2) Role scope:
       - If any role has own_only=False -> ALL (within rule above)
       - Else -> OWN (within rule above)
    3) Public:
       - `is_public=True` is returned only on SAFE methods
    OWN matching uses:
      - default owner field: create_ucp_id
      - (docstring mentions owner_fields; adjust here if you add it later)
    """

    def _supports_public(self, queryset) -> bool:
        try:
            queryset.model._meta.get_field("is_public")
            return True
        except Exception:
            return False
    def _apply_own(
        self, request, queryset, supports_public: bool, safe: bool, company_id: int
    ):
        """
        READ (SAFE):  public OR (same company AND owned by me)
        WRITE:        same company AND owned by me
        """
        ucp_id = getattr(request, "user_company_profile_id", None)

        # No owner identity -> only public for SAFE reads, none for writes
        if ucp_id is None:
            if supports_public and safe:
                return queryset.filter(Q(is_public=True))
            return queryset.none()

        owned_q = Q(company_id=company_id) & Q(create_ucp_id=ucp_id)
        if safe and supports_public:
            filter_predicate = Q(is_public=True) | owned_q
        else:
            filter_predicate = owned_q
        return queryset.filter(filter_predicate)

    def filter_queryset(self, request, queryset, view):
        supports_public = self._supports_public(queryset)
        safe = request.method in SAFE_METHODS

        company_id = getattr(request, "company_id", None)
        if company_id is None:
            # No company in request: allow only public on SAFE reads; nothing on writes
            if supports_public and safe:
                return queryset.filter(Q(is_public=True))
            return queryset.none()

        scope = effective_scope(request)
        if scope == "ALL":
            if safe and supports_public:
                filter_predicate = Q(company_id=company_id) | Q(is_public=True)
            else:
                filter_predicate = Q(company_id=company_id)
            return queryset.filter(filter_predicate)
        return self._apply_own(request, queryset, supports_public, safe, company_id)


class ApplicantOwnerScopeFilterBackend(BaseFilterBackend):
    """Filter applicant owner or the records.

    Args:
        BaseFilterBackend (class): This the Base filter backend for rest_framework.
    """
    def _apply_own(self, request, queryset):
        profile_id, _ = get_active_profile_id(request)
        if profile_id is None:
            return queryset.none()

        return queryset.filter(Q(user_profile_id=profile_id))

    def filter_queryset(self, request, queryset, view):
        return self._apply_own(request, queryset)
