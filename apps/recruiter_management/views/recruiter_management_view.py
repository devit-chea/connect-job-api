from django.db.models import Q
from django.db.models.query import Prefetch
from rest_framework.generics import ListAPIView

from apps.auth_oauth.constants.auth_constants import (
    ProfileStatus,
    RecordScope,
    UserStatus,
    UserTypes,
)
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.models.role_model import Role
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.auth_oauth.models.user_company_profile_share_model import UserCompanyProfileShareModel
from apps.auth_oauth.services.permission_service import PermissionService
from apps.base.mixins.permission_mixin import PermissionMixin
from apps.base.views.base_views import BaseModelViewSet
from apps.recruiter_management.selectors.role_selector import get_allowed_recruiter_roles
from apps.recruiter_management.serializers.recruiter_management_serializer import (
    RecruiterAdminCreateUserSerializer,
    AdminRecruiterRoleSerializer,
    UserCompanyProfileShareSerializer,
)


class RecruiterAdminCreateRecruiterView(PermissionMixin, BaseModelViewSet):
    queryset = User.objects.all()
    serializer_class = RecruiterAdminCreateUserSerializer
    search_fields = ["email", "first_name", "last_name"]
    permission_codename = "admin_recruiter_manage_user"

    def get_queryset(self):
        request = self.request
        company_id = getattr(request, "company_id", None)
        caller_ucp_id = getattr(request, "user_company_profile_id", None)

        ucp_filter = {
            "type": getattr(UserTypes, "RECRUITER", "recruiter"),
            "status": getattr(ProfileStatus, "ACTIVE", "active"),
        }
        if company_id:
            ucp_filter["company_id"] = company_id

        ucp_qs = UserCompanyProfile.objects.filter(**ucp_filter)

        permissions = PermissionService.fetch_permissions(request)
        scope = PermissionService.get_record_scope(permissions, self.permission_codename)

        if scope == RecordScope.OWN:
            ucp_qs = (
                ucp_qs.filter(create_ucp_id=str(caller_ucp_id))
                if caller_ucp_id
                else ucp_qs.none()
            )
        elif scope == RecordScope.SHARED:
            if not caller_ucp_id:
                ucp_qs = ucp_qs.none()
            else:
                shared_target_ids = UserCompanyProfileShareModel.objects.filter(
                    viewer_ucp_id=caller_ucp_id, is_deleted=False
                ).values_list("target_ucp_id", flat=True)
                ucp_qs = ucp_qs.filter(
                    Q(create_ucp_id=str(caller_ucp_id)) | Q(id__in=shared_target_ids)
                )
        # RecordScope.ALL: no extra restriction — existing company-wide behavior.

        user_ids = ucp_qs.values_list("user_id", flat=True)

        ucp_qs = ucp_qs.select_related("company", "profile").prefetch_related("roles").order_by("-id")

        qs = (
            User.objects.filter(status=getattr(UserStatus, "ACTIVE", "active"), id__in=user_ids)
            .prefetch_related(
                Prefetch(
                    "user_company_profile_user",
                    queryset=ucp_qs,
                    to_attr="active_recruiter_ucps",
                )
            )
            .distinct()
            .order_by("-id")
        )
        return qs


class AllRequestView(PermissionMixin, ListAPIView):
    queryset = Profile.objects.all()
    serializer_class = ...
    permission_codename = "admin_recruiter_manage_user"

class RecruiterAdminRolesView(PermissionMixin, BaseModelViewSet):
    queryset = Role.objects.all()
    serializer_class = AdminRecruiterRoleSerializer
    permission_codename = "admin_recruiter_manage_role"
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "create_date", "write_date"]

    def get_queryset(self):
        request = self.request
        return get_allowed_recruiter_roles(
            company_id=getattr(request, "company_id", None),
            user_company_profile_id=getattr(request, "user_company_profile_id", None),
        )


class RecruiterAdminUserShareView(PermissionMixin, BaseModelViewSet):
    """
    Lets an admin_recruiter grant another UserCompanyProfile at their company
    read-only visibility into a UserCompanyProfile record they created —
    the SHARED branch of RolePermission.record_scope on admin_recruiter_manage_user.
    """

    queryset = UserCompanyProfileShareModel.objects.filter(is_deleted=False)
    serializer_class = UserCompanyProfileShareSerializer
    permission_codename = "admin_recruiter_manage_user"

    def get_queryset(self):
        caller_ucp_id = getattr(self.request, "user_company_profile_id", None)
        return super().get_queryset().filter(create_ucp_id=str(caller_ucp_id))
