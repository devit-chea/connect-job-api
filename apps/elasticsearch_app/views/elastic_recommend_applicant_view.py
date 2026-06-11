from elasticsearch_dsl import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions, status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.base.utils.custom_filter import (
    CompanyOrUserProfileFilterBackend,
)
from apps.elasticsearch_app.serializers.recommend_applicant_serializer import (
    ApplicantScoreSerializer,
    RecommendedApplicantsResponseSerializer,
)
from apps.elasticsearch_app.services.applicant_recommend_service import (
    get_recommended_applicants,
)
from apps.job_management_app.filters.filters import JobPostFilter
from apps.job_management_app.models.job_post_model import JobPostModel
from drf_spectacular.utils import extend_schema
from apps.base.mixins.permission_mixin import PermissionMixin


class RecommendedApplicantsMixin:
    """
    Mixin to encapsulate the complex logic for retrieving, paginating,
    and serializing recommended applicants from the recommendation service.
    """

    # This Method to allow viewsets to override the score threshold if needed
    def get_min_score_threshold(self):
        """Returns the default minimum score threshold."""
        return 5

    def retrieve_recommended_applicants(self, request, is_job_state, *args, **kwargs):
        """
        Executes the recommendation service, handles pagination,
        and constructs the final response.
        """
        try:
            job_post = self.get_object()
        except Exception:
            return Response(
                {"detail": "Job post not found."}, status=status.HTTP_404_NOT_FOUND
            )

        query_string = request.query_params.get("search")
        paginator = self.paginator
        page_size = offset = None

        if paginator:
            page_size = paginator.get_page_size(request)
            page_number = request.query_params.get(paginator.page_query_param, 1)
            try:
                page_number = int(page_number)
            except:
                page_number = 1

            if page_number < 1:
                page_number = 1

            offset = (page_number - 1) * page_size

            # Force DRF to create self.page correctly
            # We pass a fake list only used for pagination metadata
            fake_total_list = list(range(0, offset + page_size))
            paginator.paginate_queryset(fake_total_list, request, view=self)

        page_applicants, total_count = get_recommended_applicants(
            job_post=job_post,
            min_score_threshold=self.get_min_score_threshold(),
            query_string=query_string,
            page_size=page_size,
            offset=offset,
            is_job_state=is_job_state,
        )

        serializer = ApplicantScoreSerializer(page_applicants, many=True)

        if paginator:
            # Create a fake list with correct total size from ES
            fake_total_list = list(range(total_count))
            # This sets paginator.page with correct next/prev behavior
            paginator.paginate_queryset(fake_total_list, request, view=self)
            response = paginator.get_paginated_response(serializer.data)
            response.data["job_id"] = job_post.id
            response.data["job_title"] = job_post.title
            response.data["total_recommend_applicants"] = total_count
            response.data["count"] = total_count
            return response

        return Response(
            {
                "job_id": job_post.id,
                "job_title": job_post.title,
                "total_recommend_applicants": total_count,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    responses={200: RecommendedApplicantsResponseSerializer},
    description="Uses Elasticsearch to find and score matching applicants who applied to job.",
)
class JobRecommendApplicantsViewSet(
    PermissionMixin, RecommendedApplicantsMixin, generics.RetrieveAPIView
):
    """
    Handles retrieval of recommended applicants for a specific JobPost.
    URL: /api/jobs/{pk}/recommend-applicants
    """

    queryset = JobPostModel.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "pk"
    permission_codename = ["admin_recruiter_manage_job_post", "recruiter_manage_job_post"]
    
    filterset_class = JobPostFilter
    filter_backends = [
        SearchFilter,
        DjangoFilterBackend,
        OrderingFilter,
        CompanyOrUserProfileFilterBackend,
    ]

    def retrieve(self, request, *args, **kwargs):
        """
        Overrides the retrieve method to delegate logic to the mixin.
        """
        # Delegate the actual work to the reusable mixin method
        return self.retrieve_recommended_applicants(
            request, is_job_state=True, *args, **kwargs
        )


@extend_schema(
    responses={200: RecommendedApplicantsResponseSerializer},
    description="Uses Elasticsearch to find and score matching all applicants, who registered.",
)
class JobRecommendAllApplicantsViewSet(
    RecommendedApplicantsMixin, generics.RetrieveAPIView
):
    """
    Handles retrieval of recommended applicants for a specific JobPost
    (presumably with a slightly different business logic or URL).
    """

    queryset = JobPostModel.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "pk"

    def retrieve(self, request, *args, **kwargs):
        """
        Overrides the retrieve method to delegate logic to the mixin.
        """
        # Delegate the actual work to the reusable mixin method
        return self.retrieve_recommended_applicants(
            request, is_job_state=False, *args, **kwargs
        )


