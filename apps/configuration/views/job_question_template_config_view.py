from django.db.models import Count, Prefetch, Q
from rest_framework import status
from rest_framework.response import Response

from apps.base.mixins.permission_mixin import PermissionMixin
from apps.base.utils.custom_filter import CompanyAndRoleScopeFilterBackend
from apps.base.views.base_views import (
    AdminRecruiterOrRecruiterBaseViewSet,
    BaseModelViewSet,
)
from apps.configuration.models.job_question_template_config_model import (
    JobQuestionTemplateConfigModel,
    JobQuestionConfigModel,
)
from apps.configuration.serializers.job_question_template_config_serializer import (
    JobQuestionTemplateConfigListSerializer,
    JobQuestionTemplateConfigDetailSerializer,
    JobQuestionTemplateConfigWriteSerializer,
    OperatorJobQuestionTemplateConfigWriteSerializer,
)


class JobQuestionTemplateConfigViewSet(
    PermissionMixin, AdminRecruiterOrRecruiterBaseViewSet
):
    queryset = (
        JobQuestionTemplateConfigModel.objects.prefetch_related("questions")
        .all()
        .order_by("-id")
    )
    filterset_fields = "__all__"
    ordering_fields = "__all__"
    search_fields = [
        "question_title",
        "question_type",
    ]
    permission_codename = [
        "recruiter_manage_job_post_question_template",
        "admin_recruiter_manage_job_post_question_template",
    ]

    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    # Annotate count question for listing template
    def get_queryset(self):
        # Prefetch only non-deleted questions
        question_qs = JobQuestionConfigModel.objects.filter(is_deleted=False)

        qs = (
            JobQuestionTemplateConfigModel.objects.filter(
                is_deleted=False
            )  # exclude deleted templates
            .prefetch_related(Prefetch("questions", queryset=question_qs))
            .order_by("-id")
        )

        if self.action == "list":
            qs = qs.annotate(
                question_count=Count(
                    "questions", filter=Q(questions__is_deleted=False)
                ),
            )
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return JobQuestionTemplateConfigListSerializer
        if self.action == "retrieve":
            return JobQuestionTemplateConfigDetailSerializer
        return JobQuestionTemplateConfigWriteSerializer

    def retrieve(self, request, *args, **kwargs):
        """
        Return template DETAIL with questions sorted by order
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data

        # Sort questions
        data["questions"] = sorted(data.get("questions", []), key=lambda x: x["order"])

        return Response(data)

    def partial_update(self, request, *args, **kwargs):
        """
        PATCH template with nested questions
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Reload instance to reflect changes
        instance.refresh_from_db()
        serializer = JobQuestionTemplateConfigDetailSerializer(instance)
        data = serializer.data

        # Sort questions
        data["questions"] = sorted(data.get("questions", []), key=lambda x: x["order"])

        return Response(data, status=status.HTTP_200_OK)


class OperatorJobQuestionTemplateConfigViewSet(PermissionMixin, BaseModelViewSet):
    queryset = (
        JobQuestionTemplateConfigModel.objects.prefetch_related("questions")
        .all()
        .order_by("-id")
    )
    permission_codename = ["operator_manage_job_post_question_template"]
    filter_backends = [
        CompanyAndRoleScopeFilterBackend
    ] + BaseModelViewSet.filter_backends

    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    # Annotate count question for listing template
    def get_queryset(self):
        # Prefetch only non-deleted questions
        question_qs = JobQuestionConfigModel.objects.filter(is_deleted=False)

        qs = (
            JobQuestionTemplateConfigModel.objects.filter(is_deleted=False)
            .prefetch_related(Prefetch("questions", queryset=question_qs))
            .order_by("-id")
        )

        if self.action == "list":
            qs = qs.annotate(
                question_count=Count(
                    "questions", filter=Q(questions__is_deleted=False)
                ),
            )
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return JobQuestionTemplateConfigListSerializer
        if self.action == "retrieve":
            return JobQuestionTemplateConfigDetailSerializer
        return OperatorJobQuestionTemplateConfigWriteSerializer

    def retrieve(self, request, *args, **kwargs):
        """
        Return template DETAIL with questions sorted by order
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data

        # Sort questions
        data["questions"] = sorted(data.get("questions", []), key=lambda x: x["order"])

        return Response(data)

    def partial_update(self, request, *args, **kwargs):
        """
        PATCH template with nested questions
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Reload instance to reflect changes
        instance.refresh_from_db()
        serializer = JobQuestionTemplateConfigDetailSerializer(instance)
        data = serializer.data

        # Sort questions
        data["questions"] = sorted(data.get("questions", []), key=lambda x: x["order"])

        return Response(data, status=status.HTTP_200_OK)
