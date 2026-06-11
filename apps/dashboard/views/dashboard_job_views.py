from collections import defaultdict

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Sum, Q
from django.utils import timezone
from django_elasticsearch_dsl_drf.filter_backends import (
    FilteringFilterBackend,
    OrderingFilterBackend,
    SearchFilterBackend,
)
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework import status, views
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import Response

from apps.activity_tracking_app.models.job_post_user_state_model import (
    JobPostUserStateModel,
)
from apps.auth_oauth.constants.auth_constants import UserTypes
from apps.base.mixins.custom_jwt_request_mixin import CustomJWTRequestMixin
from apps.base.mixins.permission_mixin import PermissionMixin
from apps.base.views.base_document_view_set import BaseDocumentViewSet
from apps.base.views.base_views import BaseListAPIView
from apps.core.pagination import CustomPagination
from apps.dashboard.mixins.dashboard_mixin import DashboardFilterMixin
from apps.dashboard.serializers.job_post_serializers import (
    ApplicantHiringStageResponseSerializer,
    ApplicantStageQueryParamsSerializer,
    JobApplicationModelSerializer,
    JobStatsQueryParamsSerializer,
    JobStatsResponseSerializer,
)
from apps.dashboard.services.job_service import DashboardService
from apps.elasticsearch_app.search.applicant_profile_document import (
    ApplicantProfileDocument,
)
from apps.elasticsearch_app.serializers.global_search_serializer import (
    ProfileDocumentSerializer,
)
from apps.job_management_app.constants.job_application_types import JobApplicationStatus
from apps.job_management_app.constants.job_post_types import JobPostStatusTypes
from apps.job_management_app.filters.filters import JobPostFilter
from apps.job_management_app.models.job_application_model import JobApplicationModel
from apps.job_management_app.models.job_post_model import JobPostModel
from apps.job_management_app.selectors.pipeline_selector import (
    get_job_pipeline_config,
    get_pipeline_steps,
)
from apps.job_management_app.serializers.dashboard_job_serializer import (
    JobPostListSerializer,
)


class DashboardRecruiterJobView(PermissionMixin, BaseListAPIView):
    serializer_class = JobPostListSerializer
    queryset = JobPostModel.objects.all().order_by("-id")
    permission_classes = [IsAuthenticated]
    filterset_class = JobPostFilter
    permission_codename = ["admin_recruiter_dashboard", "recruiter_dashboard"]

    def _access_control_validate(self, user_context):
        user_type = getattr(user_context, "user_type", None)
        supported_user_types = {
            UserTypes.ADMIN_RECRUITER.value,
            UserTypes.RECRUITER.value,
            UserTypes.OPERATOR.value,
        }
        if user_type == UserTypes.APPLICANT.value:
            raise PermissionDenied(
                "Access denied: User type 'applicant' is not permitted to use this filter."
            )
        if user_type is None:
            raise PermissionDenied("Access denied: User type is missing.")
        if user_type not in supported_user_types:
            raise PermissionDenied(f"Unsupported user type: '{user_type}'.")

    def apply_role_filter_job(self, request, queryset):
        self._access_control_validate(request)
        if request.user_type == UserTypes.RECRUITER.value:
            return queryset.filter(create_ucp_id=request.user_company_profile_id)
        return queryset

    def get_queryset(self):
        request = self.request
        company_id = getattr(request, "company_id", None)
        if not company_id:
            return JobPostModel.objects.none()
        qs = super().get_queryset().filter(is_deleted=False, company_id=company_id)

        return self.apply_role_filter_job(request, qs)


class JobStatsView(
    PermissionMixin, CustomJWTRequestMixin, views.APIView, DashboardFilterMixin
):
    permission_classes = [IsAuthenticated]
    permission_codename = ["admin_recruiter_dashboard", "recruiter_dashboard"]

    @extend_schema(
        summary="Get Job Statistics with Date Filters",
        description="Retrieves total, active, closed, and on-hold job counts with optional date and month filtering.",
        parameters=[
            OpenApiParameter(
                name="start_date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Start date (YYYY-MM-DD)",
            ),
            OpenApiParameter(
                name="end_date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="End date (YYYY-MM-DD)",
            ),
            OpenApiParameter(
                name="month",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Specific month number (1-12)",
            ),
        ],
        responses={200: JobStatsResponseSerializer},
    )
    def get(self, request):
        qp_serializer = JobStatsQueryParamsSerializer(data=request.query_params)
        if not qp_serializer.is_valid():
            return Response(qp_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        _ = qp_serializer.validated_data

        qs = JobPostModel.objects.filter(company_id=request.company_id).exclude(
            status=JobPostStatusTypes.DRAFT.value
        )
        qs = self.apply_date_filters(request, qs, date_field="post_date")
        qs = self.apply_role_filter_job(request, qs)
        month_comparison = DashboardService.get_month_comparison_stats(
            queryset=qs, time_field="post_date"
        )

        raw_data = {
            "total_jobs": qs.count(),
            "active_jobs": qs.filter(
                status=JobPostStatusTypes.ACTIVE.value,
                expire_date__gte=timezone.localdate(),
            ).count(),
            "closed_jobs": qs.filter(
                status=JobPostStatusTypes.ACTIVE.value,
                expire_date__isnull=False,
                expire_date__lt=timezone.localdate(),
            ).count(),
            "on_hold_jobs": qs.filter(status=JobPostStatusTypes.INACTIVE.value).count(),
            "month_comparison": month_comparison,
        }
        serializer = JobStatsResponseSerializer(raw_data)
        final_data = serializer.data

        return Response(final_data)


class HeadcountByCategoryView(
    PermissionMixin, CustomJWTRequestMixin, views.APIView, DashboardFilterMixin
):
    permission_classes = [IsAuthenticated]
    permission_codename = ["admin_recruiter_dashboard", "recruiter_dashboard"]

    def get_queryset(self, request):
        """
        Admin Recruiter → can see all job posts
        Recruiter → can only see job posts they created
        """
        qs = JobPostModel.objects.filter(
            status=JobPostStatusTypes.ACTIVE.value,
            is_active=True,
            company_id=request.company_id,
            company_id__isnull=False,
        )
        qs = self.apply_date_filters(request, qs, date_field="post_date")
        qs = self.apply_role_filter_job(request, qs)

        if (
            hasattr(request, "user_type")
            and request.user_type == UserTypes.RECRUITER.value
        ):
            user_ucp_id = getattr(request, "user_company_profile_id", None)
            qs = qs.filter(create_ucp_id=user_ucp_id)
        return qs

    def get(self, request):
        qs = self.get_queryset(request)

        # --- Aggregations ---
        total_headcount = qs.aggregate(total=Sum("hire_no"))["total"] or 0
        total_category_count = qs.values("category").distinct().count()

        # Group by category
        categories = (
            qs.values("category")
            .annotate(
                position_count=Count("id"),
                headcount=Sum("hire_no"),
            )
            .order_by("-headcount")
        )

        return Response(
            {
                "total_position": total_category_count,  # category
                "total_headcount": total_headcount,
                "categories": [
                    {
                        "category": item["category"] or "Unknown",
                        "positions": item["position_count"],
                        "headcount": item["headcount"] or 0,
                    }
                    for item in categories
                ],
            }
        )


class AppliedByCategoryView(
    PermissionMixin, CustomJWTRequestMixin, views.APIView, DashboardFilterMixin
):
    permission_classes = [IsAuthenticated]
    permission_codename = ["admin_recruiter_dashboard", "recruiter_dashboard"]

    def get(self, request):
        applied_qs = JobPostUserStateModel.objects.filter(
            status="applied",
            job_post__company_id=request.company_id,
            job_post__company_id__isnull=False,
        )
        applied_qs = self.apply_role_filter_applied(request, applied_qs)

        total_applied = applied_qs.count()
        if total_applied == 0:
            data = {"total_applied": 0, "categories": []}
            return Response(data)

        category_qs = applied_qs.values("job_post__category").annotate(
            applied=Count("id")
        )
        categories_list = []
        for c in category_qs:
            categories_list.append(
                {
                    "name": c["job_post__category"] or "Unknown",
                    # Calculation remains the same: (Applications in Category / Total Applications) × 100
                    "percent": round((c["applied"] / total_applied) * 100, 2),
                    "applied_count": c["applied"],
                }
            )
        # Sort the results in Python by applied count (descending)
        categories_list.sort(key=lambda item: item["applied_count"], reverse=True)
        top_3_categories = categories_list[:3]

        data = {"total_applied": total_applied, "categories": top_3_categories}

        return Response(data)


class ApplicationOverviewView(
    PermissionMixin, CustomJWTRequestMixin, views.APIView, DashboardFilterMixin
):
    permission_classes = [IsAuthenticated]
    permission_codename = ["admin_recruiter_dashboard", "recruiter_dashboard"]

    def get(self, request):
        qs = JobPostUserStateModel.objects.filter(
            status="applied",
            job_post__company_id=request.company_id,
            job_post__company_id__isnull=False,
        )
        qs = self.apply_role_filter_applied(request, qs)

        total = qs.count()
        if total == 0:
            data = {"total": 0, "types": []}
            return Response(data)

        time_types_queryset = qs.values("job_post__time_type").annotate(
            count=Count("id")
        )

        types_list = []
        for t in time_types_queryset:
            types_list.append(
                {
                    "name": t["job_post__time_type"] or "Unknown",
                    "percent": round((t["count"] / total) * 100, 2),
                    "applied_count": t["count"],
                }
            )

        types_list.sort(key=lambda item: item["applied_count"], reverse=True)
        data = {"total": total, "types": types_list}
        return Response(data)


class ApplicantMatchViewSet(BaseDocumentViewSet):
    document = ApplicantProfileDocument
    serializer_class = ProfileDocumentSerializer
    pagination_class = CustomPagination
    permission_codename = ["admin_recruiter_dashboard", "recruiter_dashboard"]

    filter_backends = [
        FilteringFilterBackend,
        OrderingFilterBackend,
        SearchFilterBackend,
    ]
    search_fields = [
        "full_name",
        "skills",
        "education_study_field",
        "work_titles",
        "current_position",
    ]
    filter_fields = {
        "is_active": "is_active",
    }
    ordering_fields = {
        "score": "_score",
        "full_name": "full_name.keyword",
    }
    ordering = ("-score",)

    def get_queryset(self):
        # 1. Get the company_id and related job titles
        company_id = getattr(self.request, "company_id", None)
        job_posts = JobPostModel.objects.filter(
            company_id=company_id,
            is_active=True,
            company_id__isnull=False,
        )
        job_titles = [job.title for job in job_posts if job.title]

        if not job_titles:
            pass  # Continue to build the query, it will just result in zero matches if done right.

        search = self.document.search().filter("term", is_active=True)

        if job_titles:
            query = Q(
                "multi_match", query=" ".join(job_titles), fields=self.search_fields
            )
            search = search.query(query)

        return search

    def list(self, request, *args, **kwargs):
        search = self.filter_queryset(self.get_queryset())

        company_id = getattr(request, "company_id", None)
        if not JobPostModel.objects.filter(
            company_id=company_id, is_active=True
        ).exists():
            return self.get_paginated_response([])

        # Standard DRF flow: paginate and serialize
        page = self.paginate_queryset(
            search.execute()
        )  # Execute the ES query only once

        if page is not None:
            serializer = self.get_serializer(page, many=True)

            # Re-fetch job titles for the post-processing step
            job_posts = JobPostModel.objects.filter(
                company_id=company_id, is_active=True, company_id__isnull=False
            )
            job_titles = [job.title for job in job_posts if job.title]

            for item in serializer.data:
                # Add the best matching job title
                item["job_title"] = self._find_best_matching_job(
                    item.get("skills_list", []), job_titles
                )
            return self.get_paginated_response(serializer.data)

        # Fallback for non-paginated requests (rare in production)
        serializer = self.get_serializer(search.execute(), many=True)
        return Response(serializer.data)

    def _find_best_matching_job(self, skills, job_titles):
        """
        Optionally match applicant skills to a specific job title.
        """
        if not skills:
            return job_titles[0] if job_titles else None
        for job_title in job_titles:
            if any(skill.lower() in job_title.lower() for skill in skills):
                return job_title
        return job_titles[0] if job_titles else None


class ApplicantHiringStageView(
    PermissionMixin, CustomJWTRequestMixin, views.APIView, DashboardFilterMixin
):
    """
    API View to generate data for the applicant funnel chart (aggregate counts).
    Filtered by job_post_id provided in the URL kwargs (optional).
    If no job_post_id is provided, it counts all applicants within the user's company scope.
    """

    permission_classes = [IsAuthenticated]
    permission_codename = ["admin_recruiter_dashboard", "recruiter_dashboard"]

    @extend_schema(
        summary="Get Applicant Funnel Statistics",
        description="Aggregates applicant counts by hiring stage for a company or specific job.",
        parameters=[
            # job_post_id comes from the URL path, not query params, so it's a path param implicitly handled by DRF
            OpenApiParameter(
                name="pipeline_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Optional specific pipeline ID to filter by.",
            ),
            # Add other relevant query params if necessary
        ],
        responses={200: ApplicantHiringStageResponseSerializer},
    )
    def get(self, request, *args, **kwargs):
        job_post_id = kwargs.get("job_post_id")
        company_id = getattr(request, "company_id", None)
        pipeline_id_qp = request.query_params.get("pipeline_id", None)

        qp_serializer = ApplicantStageQueryParamsSerializer(data=request.query_params)
        if not qp_serializer.is_valid():
            return Response(qp_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        filters = Q(status=JobApplicationStatus.ACTIVE) & Q(
            job_post__company_id=company_id,
            job_post__company_id__isnull=False,
        )

        if job_post_id:
            filters &= Q(job_post_id=job_post_id)

        # # Get Default or Company Config Pipeline
        pipeline_config_id = get_job_pipeline_config(company_id, pipeline_id_qp)

        if not pipeline_config_id:
            return Response(
                {
                    "total_applicants": 0,
                    "funnel_stages": [],
                    "message": "No pipeline config found.",
                }
            )

        qs = JobApplicationModel.objects.filter(filters)
        base_qs = self.apply_role_filter_applied(request, qs)

        total_applicants_by_pipeline = JobApplicationModel.objects.filter(
            status=JobApplicationStatus.ACTIVE,
            job_post__company_id=company_id,
            job_post__company_id__isnull=False,
            pipeline_config_id=pipeline_config_id,
        ).count()
        total_applicants = base_qs.count()

        all_steps = get_pipeline_steps(pipeline_config_id)

        combined_funnel_map = defaultdict(
            lambda: {"stage_name": "N/A", "count": 0, "order": 0}
        )

        for step in all_steps:
            step_name = step["name"]
            combined_funnel_map[step_name] = {
                "id": step["id"],
                "stage_name": step_name,
                "count": 0,  # Initialize count to 0
                "order": step["order"],
                "color": step["color"],
            }

        applicant_counts = base_qs.values("pipeline_step__name").annotate(
            applicant_count=Count("id")
        )

        for count_item in applicant_counts:
            step_name = count_item["pipeline_step__name"]
            if step_name in combined_funnel_map:
                combined_funnel_map[step_name]["count"] = count_item["applicant_count"]

        formatted_funnel = sorted(
            list(combined_funnel_map.values()), key=lambda x: x["order"]
        )

        if total_applicants == 0:
            formatted_funnel = [{**step, "count": 0} for step in formatted_funnel]

        raw_response_data = {
            "pipeline_config_id": pipeline_config_id,
            "total_applicants": total_applicants,
            "total_applicants_by_pipeline": total_applicants_by_pipeline,
            "funnel_stages": formatted_funnel,
        }

        response_serializer = ApplicantHiringStageResponseSerializer(raw_response_data)
        return Response(response_serializer.data)


class InterviewScheduleView(PermissionMixin, BaseListAPIView, DashboardFilterMixin):
    permission_classes = [IsAuthenticated]
    queryset = JobApplicationModel.objects.all().order_by("-apply_date")
    serializer_class = JobApplicationModelSerializer
    permission_codename = ["admin_recruiter_dashboard", "recruiter_dashboard"]

    filter_backends = [SearchFilter, OrderingFilter]

    def get_queryset(self):
        company_id = getattr(self.request, "company_id", None)

        qs = self.queryset

        qs = qs.filter(
            pipeline_step_name="Interview",
            status=JobApplicationStatus.ACTIVE,
            job_post__company_id=company_id,
            job_post__company_id__isnull=False,
        )

        return self.apply_role_filter_applied(self.request, qs)
