from apps.base.mixins.permission_mixin import PermissionMixin
from apps.base.models.company_model import Company
from apps.base.serializers.admin_company_serializer import (
    AdminCompanySerializer,
    AdminCompanyDetailSerializer,
)
from apps.base.views.base_views import BaseModelViewSet


class AdminCompanyView(PermissionMixin, BaseModelViewSet):
    FIELDS = ["name", "email", "phone_number", "is_active", "industry"]
    permission_codename = "operator_manage_company"
    queryset = Company.objects.exclude(code="DEFAULT")
    serializer_class = AdminCompanySerializer
    filterset_fields = FIELDS
    search_fields = FIELDS

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AdminCompanyDetailSerializer
        return AdminCompanySerializer
