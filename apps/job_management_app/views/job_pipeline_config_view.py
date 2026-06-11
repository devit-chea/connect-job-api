from django.db.models import Prefetch, Exists, OuterRef
from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from apps.base.mixins.permission_mixin import PermissionMixin
from apps.base.utils.custom_filter import CompanyAndRoleScopeFilterBackend
from apps.base.views.base_views import (
    AdminRecruiterOrRecruiterBaseViewSet,
    BaseModelViewSet,
    BaseRetrieveAPIView,
)
from apps.core.exceptions.base_exceptions import BadRequestException
from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineConfigModel,
    JobPipelineStatusConfigModel,
    JobPipelineStepStatusConfigModel,
    JobPipelineConfigStepModel,
)
from apps.job_management_app.models.job_post_model import JobPostModel
from apps.job_management_app.serializers.job_pipeline_config_serializer import (
    JobPipelineConfigReadSerializer,
    JobPipelineConfigWriteSerializer,
    JobPipelineStatusConfigSerializer,
    OperatorJobPipelineStatusConfigSerializer,
    OperatorJobPipelineConfigWriteSerializer,
    StepAllowedStatusReadSerializer,
    JobPipelineConfigDetailSerializer,
)
from apps.job_management_app.services.job_pipeline_service import JobPipelineService

_PIPELINE_IN_USE_ANNOTATION = Exists(
    JobPostModel.objects.filter(
        job_pipeline_config_id=OuterRef("pk")
    )
)
class JobPipelineConfigView(PermissionMixin, AdminRecruiterOrRecruiterBaseViewSet):
    queryset = JobPipelineConfigModel.objects.prefetch_related(
        Prefetch(
            "steps",
            queryset=JobPipelineConfigStepModel.objects.order_by("order"),
        )
    ).order_by("-is_default", "is_public")

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action in ["retrieve", "update", "partial_update"]:
            if self.action in ["retrieve", "update", "partial_update"]:
                qs = qs.annotate(is_in_use=_PIPELINE_IN_USE_ANNOTATION)
        return qs

    filterset_fields = "__all__"
    ordering_fields = "__all__"
    search_fields = [
        "name",
        "code",
    ]
    permission_codename = [
        "admin_recruiter_manage_job_post_pipeline",
        "recruiter_manage_job_post_pipeline",
    ]

    def get_serializer_class(self):
        if self.action == "list":
            return JobPipelineConfigReadSerializer
        if self.action == "retrieve":
            return JobPipelineConfigDetailSerializer
        return JobPipelineConfigWriteSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()

        if self.action in ["update", "partial_update"]:
            instance = self.get_object()
            context["pipeline_in_use"] = instance.is_in_use
        return context

    def perform_update(self, serializer):
        instance = self.get_object()

        if instance.is_public and instance.company_id != self.request.company_id:
            raise PermissionDenied("Cannot modify public config")

        serializer.save()

    def perform_destroy(self, instance):
        if instance.is_public and instance.company_id != self.request.company_id:
            raise PermissionDenied("Cannot delete public config")

        JobPipelineService.check_pipeline_usage(instance)
        return super().perform_destroy(instance)


class OperatorJobPipelineConfigView(PermissionMixin, BaseModelViewSet):
    queryset = JobPipelineConfigModel.objects.all()
    filter_backends = [
        CompanyAndRoleScopeFilterBackend
    ] + BaseModelViewSet.filter_backends
    permission_codename = ["operator_manage_job_post_pipeline"]
    filterset_fields = "__all__"
    ordering_fields = "__all__"
    search_fields = [
        "name",
        "code",
    ]
    
    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return JobPipelineConfigReadSerializer
        return OperatorJobPipelineConfigWriteSerializer

    def perform_update(self, serializer):
        instance = self.get_object()
        JobPipelineService.check_pipeline_usage(instance)
        return super().perform_update(serializer)

    def perform_destroy(self, instance):
        JobPipelineService.check_pipeline_usage(instance)
        return super().perform_destroy(instance)


class JobPipelineStatusConfigView(PermissionMixin, BaseModelViewSet):
    queryset = JobPipelineStatusConfigModel.objects.all()
    search_fields = ["id", "name", "description"]
    filter_backends = [
        CompanyAndRoleScopeFilterBackend
    ] + BaseModelViewSet.filter_backends
    permission_codename = [
        "recruiter_manage_job_pipeline_status_config",
        "admin_recruiter_manage_job_pipeline_status_config",
    ]
    serializer_class = JobPipelineStatusConfigSerializer


class OperatorJobPipelineStatusConfigView(PermissionMixin, BaseModelViewSet):
    queryset = JobPipelineStatusConfigModel.objects.all()
    filter_backends = [
        CompanyAndRoleScopeFilterBackend
    ] + BaseModelViewSet.filter_backends
    permission_codename = ["operator_manage_job_post_pipeline"]
    serializer_class = OperatorJobPipelineStatusConfigSerializer


class StepStatusesListView(PermissionMixin, BaseRetrieveAPIView):
    serializer_class = StepAllowedStatusReadSerializer
    pagination_class = None
    permission_codename = [
        "recruiter_manage_job_pipeline_status_config",
        "admin_recruiter_manage_job_pipeline_status_config",
    ]
    filter_backends = []

    def get_queryset(self):
        step_id = self.kwargs.get("pk")
        return (
            JobPipelineStepStatusConfigModel.objects.select_related("status")
            .filter(
                step_id=step_id,
                is_deleted=False,
                step__is_deleted=False,
                status__is_deleted=False,
                status__is_active=True,
            )
            .order_by("status_id")
        )

    def get(self, request, *args, **kwargs):
        step_id = kwargs.get("pk")
        qs = self.get_queryset()

        if not qs.exists():
            step_exists = JobPipelineConfigStepModel.objects.filter(
                pk=step_id, is_deleted=False
            ).exists()
            if not step_exists:
                raise BadRequestException("Step not found")
        data = self.get_serializer(qs, many=True).data
        return Response(data, status=status.HTTP_200_OK)
