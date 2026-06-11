import logging
from collections import defaultdict

from django.db.models import (
    Count,
    OuterRef,
    Subquery,
    IntegerField,
)
from django.db.models.functions import Coalesce
from django.db.models.query_utils import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from wdg_storage.base import get_file_url

from apps.activity_tracking_app.constants.job_activity_types import (
    ActivityTrackingTypes,
)
from apps.activity_tracking_app.mixins.track_activity_decorator import (
    track_activity_job_post,
)
from apps.auth_oauth.constants.auth_constants import UserStatus
from apps.base.decorators.permission_decorator import permission
from apps.base.mixins.permission_mixin import PermissionMixin
from apps.base.utils.file_management_util import FileURLService, _to_uuid
from apps.base.utils.custom_filter import CompanyOrUserProfileFilterBackend, CompanyAndRoleScopeFilterBackend, \
    JobPostRecruiterScopeFilterBackend
from apps.base.views.base_views import (
    BaseListAPIView,
    BaseModelViewSet,
    BasePatchAPIView,
    BaseReadOnlyViewSet,
    BaseUpdateAPIView,
)
from apps.core.pagination import CustomPagination
from apps.job_management_app.constants.job_post_types import JobPostStatusTypes
from apps.job_management_app.constants.message_constants import JobMsg
from apps.job_management_app.filters.filters import JobPostFilter
from apps.job_management_app.filters.job_post_filters import JobPostByCompanyFilter
from apps.job_management_app.models.job_application_model import JobApplicationModel
from apps.job_management_app.models.job_category_model import JobCategoryModel
from apps.job_management_app.models.job_pipeline_config_model import JobPipelineConfigStepModel
from apps.job_management_app.models.job_post_model import JobPostModel
from apps.job_management_app.models.job_question_model import JobPostQuestionModel
from apps.job_management_app.serializers.job_application_serializer import (
    JobApplicationRequestSerializer,
    RecruiterPipelineUpdateSerializer,
    RecruiterUpdateStatusPipelineSerializer,
)
from apps.job_management_app.serializers.job_post_assign_serializer import CompanyRecruiterPickerSerializer
from apps.job_management_app.serializers.job_post_save_unsave_serializer import (
    JobPostSaveUnsaveWriteSerializer,
)
from apps.job_management_app.serializers.job_post_serializer import (
    JobPostSerializer,
    JobPostQuestionSerializer,
    JobPostListSerializer,
    JobPostDetailSerializer,
    CountsQuerySerializer,
    JobCountSerializer,
    CategorySerializer,
    JobPostStatusUpdateSerializer,
)
from apps.job_management_app.services.job_application_services import (
    JobApplicationServices,
)

logger = logging.getLogger(__name__)


class ApplicantJobPostView(BaseReadOnlyViewSet):
    """
    Public/applicant-facing endpoints:
    - list / retrieve / public_detail
    - apply / save / unsave
    """

    queryset = JobPostModel.objects.all().order_by("-id")
    serializer_class = JobPostSerializer
    filter_backends = [
        SearchFilter,
        DjangoFilterBackend,
        OrderingFilter,
        CompanyOrUserProfileFilterBackend,
    ]
    filterset_class = JobPostFilter
    ordering_fields = ["id", "create_date"]
    ordering = ["-id"]
    ACTION_SERIALIZERS = {
        "apply": JobApplicationRequestSerializer,
        "list": JobPostListSerializer,
        "retrieve": JobPostDetailSerializer,
        "public_detail": JobPostDetailSerializer,
        "save_job": JobPostSaveUnsaveWriteSerializer,
        "unsave_job": JobPostSaveUnsaveWriteSerializer,
    }

    def get_serializer_class(self):
        return self.ACTION_SERIALIZERS.get(self.action, super().get_serializer_class())

    def get_permissions(self):
        if self.action == "public_detail":
            return [AllowAny()]
        return [IsAuthenticated()]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["get"],
        url_path="public_detail",
        permission_classes=[AllowAny],
    )
    @track_activity_job_post(ActivityTrackingTypes.VIEW.value)
    def public_detail(self, request, pk=None):
        job_post = self.get_object()
        serializer = self.get_serializer(job_post, context={"request": request})
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="apply")
    @permission(permission_codename="applicant_manage_profile")
    @track_activity_job_post(ActivityTrackingTypes.APPLY.value)
    def apply(self, request, pk=None):
        if not request.user.is_authenticated:
            raise PermissionDenied(JobMsg.DENIED_ANONYMOUS)
        serializer = JobApplicationRequestSerializer(
            data=request.data, context={"request": request, "job_post_id": pk}
        )
        serializer.is_valid(raise_exception=True)
        JobApplicationServices.apply_to_job(
            request=request,
            job_post_id=pk,
            validated_data=serializer.validated_data,
        )
        return Response(
            {"detail": "Application submitted successfully."},
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=None,
        responses={201: OpenApiTypes.OBJECT},
        summary="Save a job post",
        description="Saves the specified job post for the current authenticated user.",
    )
    @action(detail=True, methods=["post"], url_path="save")
    @permission(permission_codename="applicant_manage_profile")
    @track_activity_job_post(ActivityTrackingTypes.SAVE.value)
    def save_job(self, request, pk):
        if not request.user.is_authenticated:
            raise PermissionDenied(JobMsg.DENIED_ANONYMOUS)
        serializer = JobPostSaveUnsaveWriteSerializer(
            data={"job_post_id": pk, "activity_type": "save"},
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        return Response(
            {"detail": "Job saved successfully."}, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        request=None,
        responses={200: OpenApiTypes.OBJECT},
        summary="Unsave a job post",
        description="Removes the specified job post from the user's saved list.",
    )
    @action(detail=True, methods=["post"], url_path="unsave")
    @track_activity_job_post(ActivityTrackingTypes.UNSAVE.value)
    def unsave_job(self, request, pk):
        if not request.user.is_authenticated:
            raise PermissionDenied(JobMsg.DENIED_ANONYMOUS)
        serializer = JobPostSaveUnsaveWriteSerializer(
            data={"job_post_id": pk, "activity_type": "unsave"},
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        return Response(
            {"detail": "Job unsaved successfully."}, status=status.HTTP_201_CREATED
        )

class RecruiterJobPostStatusUpdateView(PermissionMixin, BaseUpdateAPIView):
    queryset = JobPostModel.objects.all()
    serializer_class = JobPostStatusUpdateSerializer
    permission_codename = [
        "admin_recruiter_manage_job_post",
        "recruiter_manage_job_post",
    ]
    filter_backends = [
        CompanyAndRoleScopeFilterBackend,
        CompanyOrUserProfileFilterBackend,
    ]

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(
            {"message": "Job status updated successfully."}, status=status.HTTP_200_OK
        )


class RecruiterJobPostView(PermissionMixin, BaseModelViewSet):
    """
    Recruiter-facing endpoints:
    - list / retrieve
    - list_by_recruiter
    - update_application_pipeline
    """

    queryset = JobPostModel.objects.all().order_by("-id")
    serializer_class = JobPostSerializer
    permission_codename = [
        "admin_recruiter_manage_job_post",
        "recruiter_manage_job_post",
    ]
    filter_backends = [
        JobPostRecruiterScopeFilterBackend,
        SearchFilter,
        DjangoFilterBackend,
        OrderingFilter,
    ]
    filterset_class = JobPostFilter
    ordering_fields = ["id", "create_date"]
    ordering = ["-id"]
    ACTION_SERIALIZERS = {
        "list": JobPostListSerializer,
        "retrieve": JobPostDetailSerializer,
        "update_application_pipeline": RecruiterPipelineUpdateSerializer,
    }
    search_fields = [
        "title",
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        ucp_id = self.request.query_params.get("created_by", None)
        if ucp_id:
            qs = qs.filter(create_ucp_id=ucp_id)
        return qs

    def get_serializer_class(self):
        return self.ACTION_SERIALIZERS.get(self.action, super().get_serializer_class())

    @action(
        detail=True,
        methods=["patch"],
        url_path=r"applications/(?P<application_id>[0-9]+)/pipeline",
    )
    @permission(
        permission_codename=["admin_recruiter_applicant", "recruiter_applicant"]
    )
    def update_application_pipeline(self, request, pk=None, application_id=None):
        from apps.job_management_app.models.job_post_assigned_recruiter_model import JobPostAssignedRecruiterModel
        ucp_id = str(request.user_company_profile_id)
        try:
            application = JobApplicationModel.objects.select_related("job_post").get(
                pk=application_id,
                job_post_id=pk,
                is_deleted=False,
            )
        except JobApplicationModel.DoesNotExist:
            raise ValidationError({"detail": "Application not found."})
        job_post = application.job_post
        is_owner = str(job_post.create_ucp_id) == ucp_id
        is_assigned = JobPostAssignedRecruiterModel.objects.filter(
            job_post=job_post, assigned_ucp_id=ucp_id, is_deleted = False
        ).exists()
        if not (is_owner or is_assigned):
            raise ValidationError({"detail": "You are not authorized to manage this job's applications."})

        serializer = self.get_serializer(
            data=request.data, context={"request": request, "application": application}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = JobApplicationServices.update_pipeline(
            job_post_id=int(pk),
            application_id=int(application_id),
            status=data["status"],
            actor=request.user,
            actor_profile_id=request.profile_id,
        )
        response = RecruiterUpdateStatusPipelineSerializer(result)
        return Response(response.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="application-status-overview")
    @permission(permission_codename=["admin_recruiter_applicant", "recruiter_applicant"])
    def application_status_overview(self, request, pk=None):
        job_post = self.get_object()

        pipeline_config = job_post.job_pipeline_config
        if not pipeline_config:
            return Response({"total": 0, "stages": []})

        steps = list(
            JobPipelineConfigStepModel.objects
            .filter(pipeline_config=pipeline_config, is_active=True)
            .prefetch_related("allowed_statuses")
            .order_by("order")
        )

        app_counts = list(
            JobApplicationModel.objects
            .filter(job_post_id=pk, is_deleted=False)
            .values("pipeline_step_id", "pipeline_status_id")
            .annotate(count=Count("id"))
        )
        count_map = {
            (row["pipeline_step_id"], row["pipeline_status_id"]): row["count"]
            for row in app_counts
        }
        total = sum(row["count"] for row in app_counts)

        step_totals = defaultdict(int)
        for (step_id, _), count in count_map.items():
            if step_id is not None:
                step_totals[step_id] += count

        stages = []
        for step in steps:
            statuses = [
                {
                    "status_id": s.id,
                    "status_name": s.name,
                    "count": count_map.get((step.id, s.id), 0),
                }
                for s in step.allowed_statuses.all()
            ]
            stages.append({
                "step_id": step.id,
                "step_name": step.name,
                "step_color": step.color,
                "order": step.order,
                "total": step_totals[step.id],
                "statuses": statuses,
            })

        return Response({"total": total, "stages": stages})
class RecruiterApplicationPipelineUpdateView(BasePatchAPIView, PermissionMixin):
    permission_codename = ["admin_recruiter_applicant", "recruiter_applicant"]
    serializer_class = RecruiterPipelineUpdateSerializer

    def get_object(self):
        job_post_id = self.kwargs["job_post_id"]
        application_id = self.kwargs["application_id"]

        return get_object_or_404(
            JobApplicationModel,
            pk=application_id,
            job_post_id=job_post_id,
            is_deleted=False,
            create_ucp_id=self.request.user_company_profile_id,
            create_uid=self.request.profile_id,
        )

    def patch(self, request, *args, **kwargs):
        application = self.get_object()

        serializer = self.serializer_class(
            application,
            data=request.data,
            partial=True,
            context={"request": request, "application": application},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = JobApplicationServices.update_pipeline(
            job_post_id=int(self.kwargs["job_post_id"]),
            application_id=int(self.kwargs["application_id"]),
            status=data["status"],
            actor=request.user,
            actor_profile_id=request.profile_id,
        )

        response_data = RecruiterUpdateStatusPipelineSerializer(result).data
        return Response(response_data, status=status.HTTP_200_OK)

class JobPostQuestionView(BaseModelViewSet):
    serializer_class = JobPostQuestionSerializer
    pagination_class = None

    def get_queryset(self, *args, **kwargs):
        job_post_id = self.kwargs.get("pk")

        if not JobPostModel.objects.filter(id=job_post_id).exists():
            raise NotFound("Job post not found.")

        return JobPostQuestionModel.objects.filter(
            job_post_id=job_post_id, is_deleted=False
        ).order_by("order")


class JobPostCountsView(GenericAPIView):
    """
    GET /api/job-posts/counts?by=location|category|company
    default: by = location
    Options:
      - sort=count|alpha (default: count)
      - exclude_null=true|false (default true)
      - paging=true|false (default true)
    """

    permission_classes = [AllowAny]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        return JobCountSerializer

    def _base_qs(self, request):
        qs = self.filter_queryset(JobPostModel.objects.all())
        today = timezone.localdate()
        return qs.filter(
            Q(is_deleted=False),
            Q(is_active=True),
            Q(status="ACTIVE"),
            Q(expire_date__isnull=True) | Q(expire_date__gte=today),
        )

    def _prepare_response(self, items, use_paging):
        if use_paging == "true":
            page = self.paginate_queryset(items)
            ser = self.get_serializer(page, many=True)
            return self.get_paginated_response(ser.data)
        else:
            ser = self.get_serializer(items, many=True)
            return Response(
                {
                    "count": len(items),
                    "results": ser.data,
                }
            )

    def _get_counts_by_company(self, qs, exclude_null):
        if exclude_null:
            qs = qs.exclude(company__isnull=True)
        name_key = "company__name"
        rows = list(qs.values(name_key).annotate(count=Count("id")).order_by("-count"))
        return [{"name": r.get(name_key), "count": r["count"]} for r in rows]

    def _get_counts_by_industry(self, qs, exclude_null):
        if exclude_null:
            qs = qs.exclude(company__industry__isnull=True).exclude(
                company__industry=""
            )
        name_key = "company__industry"
        rows = list(
            qs.values("company__industry")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        return [{"name": r.get(name_key), "count": r["count"]} for r in rows]

    def _get_counts_by_category(self, qs, exclude_null):
        qs = qs.annotate(
            category_name_resolved=Coalesce("job_category__name", "category")
        )
        if exclude_null:
            qs = qs.exclude(category_name_resolved__isnull=True).exclude(
                category_name_resolved=""
            )
        rows = list(
            qs.values("job_category_id", "category_name_resolved")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        return [
            {
                "id": r["job_category_id"],
                "name": r["category_name_resolved"],
                "count": r["count"],
            }
            for r in rows
        ]

    def _get_counts_by_location(self, qs, exclude_null):
        if exclude_null:
            qs = qs.exclude(location__isnull=True).exclude(location="")
        rows = list(
            qs.values("job_location_id", "location")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        return [
            {"id": r["job_location_id"], "name": r["location"], "count": r["count"]}
            for r in rows
        ]

    def _get_counts_by_time_type(self, qs, exclude_null):
        if exclude_null:
            qs = qs.exclude(time_type__isnull=True).exclude(time_type="")
        rows = list(
            qs.values("time_type").annotate(count=Count("id")).order_by("-count")
        )
        return [{"name": r["time_type"], "count": r["count"]} for r in rows]

    def _get_counts_by_job_level(self, qs, exclude_null):
        if exclude_null:
            qs = qs.exclude(job_level__isnull=True).exclude(job_level="")
        rows = list(
            qs.values("job_level").annotate(count=Count("id")).order_by("-count")
        )
        return [{"name": r["job_level"], "count": r["count"]} for r in rows]

    @extend_schema(
        summary="Counts of active job posts by location, category, company, industry, time_type, job_level",
        parameters=[CountsQuerySerializer],
    )
    def get(self, request, *args, **kwargs):
        by = self.kwargs.get("by")
        exclude_null = (
            request.query_params.get("exclude_null", "true").lower() != "false"
        )
        use_paging = request.query_params.get("paging")
        qs = self._base_qs(request)

        # Map 'by' values to specific handler methods
        handlers = {
            "company": self._get_counts_by_company,
            "industry": self._get_counts_by_industry,
            "category": self._get_counts_by_category,
            "location": self._get_counts_by_location,
            "time_type": self._get_counts_by_time_type,
            "job_level": self._get_counts_by_job_level,
        }

        handler = handlers.get(by)
        if handler:
            items = handler(qs, exclude_null)
            return self._prepare_response(items, use_paging)
        else:
            return Response(
                {"detail": "invalid type"}, status=status.HTTP_400_BAD_REQUEST
            )


class CompanyJobPostListView(BaseListAPIView):
    serializer_class = JobPostSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_class = JobPostByCompanyFilter
    filter_backends = [
        SearchFilter,
        DjangoFilterBackend,
        OrderingFilter,
    ]
    search_fields = ["title", "location", "category"]

    def get_queryset(self):
        company_id = self.kwargs.get("company_id")
        if not company_id:
            return JobPostModel.objects.none()
        try:
            today = timezone.localdate()
            return JobPostModel.objects.filter(
                company_id=company_id,
                is_deleted=False,
                is_active=True,
                status=JobPostStatusTypes.ACTIVE.value,
                expire_date__gte=today,
            ).order_by("-post_date")
        except Exception as e:
            logger.error(f"Error filtering job posts: {e}")
            return JobPostModel.objects.none()


class RecruiterJobPostListView(BaseListAPIView):
    """
    API view to list all JobPostModels belonging to a specific Recruiter ID.
    The create_ucp_id is extracted from the URL path.
    """

    serializer_class = JobPostListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_class = JobPostFilter
    filter_backends = [
        SearchFilter,
        DjangoFilterBackend,
        OrderingFilter,
    ]
    search_fields = ["title", "location"]

    def get_queryset(self):
        company_id = getattr(self.request, "company_id", None)
        create_ucp_id = self.kwargs.get("create_ucp_id")  # ← GET PARAM FROM PATH

        if not company_id:
            logger.warning("Company ID not provided in request.")
            return JobPostModel.objects.none()

        if not create_ucp_id:
            logger.warning("create_ucp_id not provided in URL path.")
            return JobPostModel.objects.none()

        return self._get_filtered_queryset(company_id, create_ucp_id)

    def _get_filtered_queryset(self, company_id, create_ucp_id):
        try:
            queryset = (
                JobPostModel.objects.filter(
                    company_id=company_id,
                    create_ucp_id=create_ucp_id,
                    is_deleted=False,
                    is_active=True,
                )
                .order_by("-post_date")
            )
            return queryset
        except Exception:
            logger.exception(
                "Error retrieving job posts for company_id=%s, create_ucp_id=%s",
                company_id,
                create_ucp_id,
            )
            return JobPostModel.objects.none()


@extend_schema(
    summary="List Category Count Jobs",
    parameters=[CategorySerializer],
)
class JobPostCategoryListView(GenericAPIView):
    permission_classes = [AllowAny]
    pagination_class = CustomPagination
    serializer_class = JobCountSerializer

    def get(self, request, *args, **kwargs):
        today = timezone.localdate()

        # base job filter
        base_job_filter = Q(
            is_deleted=False,
            is_active=True,
            status="ACTIVE",
        ) & (
            Q(expire_date__isnull=True)
            | Q(expire_date__gte=today)
        )

        # total jobs count
        total_jobs_count = JobPostModel.objects.filter(
            base_job_filter
        ).count()

        # subquery count by category string
        job_count_subquery = (
            JobPostModel.objects.filter(
                base_job_filter,
                category=OuterRef("name"),
            )
            .values("category")
            .annotate(total=Count("id"))
            .values("total")[:1]
        )

        # ALL categories including count=0
        qs = JobCategoryModel.objects.annotate(
            count=Coalesce(
                Subquery(job_count_subquery, output_field=IntegerField()),
                0,
            )
        )

        # Optional search
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(name__icontains=search)

        # resolve all category image URLs in one DB query
        categories = list(qs)
        file_map = FileURLService.map_by_file_ids(
            filter(None, (c.profile_picture_id for c in categories))
        )

        mapped = []
        for cat in categories:
            pid = _to_uuid(cat.profile_picture_id)
            mapped.append(
                {
                    "id": cat.id,
                    "name": cat.name,
                    "count": cat.count,
                    "profile_image_url": (file_map.get(pid) or {}).get("file_path"),
                }
            )

        page = self.paginate_queryset(mapped)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(
                serializer.data
            )
            response.data["total_jobs_count"] = total_jobs_count
            return response
        serializer = self.get_serializer(mapped, many=True)

        return Response(
            {
                "total_jobs_count": total_jobs_count,
                "results": serializer.data,
            }
        )


class OperatorJobPostView(PermissionMixin, BaseReadOnlyViewSet):
    queryset = JobPostModel.objects.exclude(status="DRAFT").order_by("-id")
    permission_codename = ["operator_manage_job_post"]

    FIELDS = [
        "title",
        "job_level",
        "year_of_experience",
    ]
    filterset_fields = FIELDS
    search_fields = FIELDS
    ordering_fields = ["id", "post_date"]

    serializer_class = JobPostSerializer
    # filterset_class = JobPostFilter
    ACTION_SERIALIZERS = {
        "list": JobPostListSerializer,
        "retrieve": JobPostDetailSerializer,
    }

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["include_cover"] = False
        return context

    def get_serializer_class(self):
        return self.ACTION_SERIALIZERS.get(self.action, super().get_serializer_class())

class CompanyRecruitersListView(PermissionMixin, BaseListAPIView):
    """
    GET /recruiter/company-recruiters
    Returns all active recruiters in the same company as the requester
    """
    permission_codename = ["admin_recruiter_manage_job_post", "recruiter_manage_job_post"]
    serializer_class = CompanyRecruiterPickerSerializer
    filter_backends = [SearchFilter]
    search_fields = ["profile__full_name", "profile__email"]
    pagination_class = None

    def get_queryset(self):
        from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
        from apps.auth_oauth.constants.auth_constants import UserTypes

        company_id = getattr(self.request, "company_id", None)
        current_ucp_id = getattr(self.request, "user_company_profile_id", None)

        if not company_id:
            return UserCompanyProfile.objects.none()

        return (
            UserCompanyProfile.objects
            .filter(
                company_id=company_id,
                type__in=[UserTypes.RECRUITER.value, UserTypes.ADMIN_RECRUITER.value],
                user__status=UserStatus.ACTIVE,
            )
            .exclude(id=current_ucp_id)
            .select_related("profile")
            .order_by("profile__full_name")
        )
