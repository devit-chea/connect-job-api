from rest_framework.permissions import AllowAny
from apps.base.views.base_views import BaseModelViewSet, BaseListAPIView
from apps.job_management_app.models.job_category_model import JobCategoryModel
from apps.job_management_app.serializers.job_category_serializer import (
    JobCategorySerializer,
)
from apps.base.mixins.permission_mixin import PermissionMixin


class JobCategoryView(PermissionMixin, BaseModelViewSet):
    model = JobCategoryModel
    queryset = JobCategoryModel.objects.all()
    serializer_class = JobCategorySerializer
    permission_codename = "operator_manage_job_config"


class JobCategoryPublicView(BaseListAPIView):
    model = JobCategoryModel
    queryset = JobCategoryModel.objects.all()
    serializer_class = JobCategorySerializer
    permission_classes = [AllowAny]

    filterset_fields = [
        "name",
    ]
    search_fields = [
        "name",
    ]

    def get_queryset(self):
        return JobCategoryModel.objects.filter(is_deleted=False)
