from django.db.models.query import Prefetch
from rest_framework.generics import ListAPIView

from apps.auth_oauth.constants.auth_constants import (
    ProfileStatus,
    UserStatus,
    UserTypes,
)
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.models.role_model import Role
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.base.mixins.permission_mixin import PermissionMixin
from apps.base.views.base_views import BaseModelViewSet
from apps.recruiter_management.serializers.recruiter_management_serializer import (
    RecruiterAdminCreateUserSerializer,
    AdminRecruiterRoleSerializer,
)


class RecruiterAdminCreateRecruiterView(PermissionMixin, BaseModelViewSet):
    queryset = User.objects.all()
    serializer_class = RecruiterAdminCreateUserSerializer
    search_fields = ["email", "first_name", "last_name"]
    permission_codename = "admin_recruiter_manage_user"

    def get_queryset(self):
        request = self.request
        company_id = getattr(request, "company_id", None)

        ucp_filter = {
            "type": getattr(UserTypes, "RECRUITER", "recruiter"),
            "status": getattr(ProfileStatus, "ACTIVE", "active"),
        }
        if company_id:
            ucp_filter["company_id"] = company_id

        ucp_qs = (
            UserCompanyProfile.objects.filter(**ucp_filter)
            .select_related("company", "profile")
            .prefetch_related("roles")
            .order_by("-id")
        )

        qs = (
            User.objects.filter(status=getattr(UserStatus, "ACTIVE", "active"))
            .filter(
                **{f"user_company_profile_user__{k}": v for k, v in ucp_filter.items()}
            )
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
        company_id = getattr(self.request, "company_id", None)
        qs = super().get_queryset()
        if company_id:
            return qs.filter(company_id=company_id, active=True)
        return Role.objects.none()
