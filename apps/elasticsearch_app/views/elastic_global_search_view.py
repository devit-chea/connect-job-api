import json
import logging
from drf_spectacular.utils import OpenApiParameter, extend_schema
from elasticsearch_dsl import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from django_elasticsearch_dsl_drf.filter_backends import (
    DefaultOrderingFilterBackend,
    FilteringFilterBackend,
)
from apps.auth_oauth.constants.auth_constants import UserTypes
from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.models.work_experience_model import WorkExperience
from apps.auth_oauth.serializers.profile_serializer import PeopleProfileDetailSerializer
from apps.base.views.base_document_view_set import BasePublicDocumentViewSet
from apps.core.exceptions.base_exceptions import BadRequestException
from apps.core.pagination import CustomPagination
from apps.elasticsearch_app.search.global_search_document import (
    ProfileDocument,
)
from apps.elasticsearch_app.serializers.global_search_serializer import (
    CompanyDocumentSerializer,
    GlobalSearchResponseSerializer,
    ProfileDocumentSerializer,
)
from apps.elasticsearch_app.serializers.job_post_document_serializer import (
    JobPostDocumentSerializer,
)
from apps.elasticsearch_app.services.global_search_service import GlobalSearchService
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.viewsets import GenericViewSet

from apps.elasticsearch_app.services.job_recommendation_service import (
    JobRecommendationService,
)
from rest_framework import permissions

logger = logging.getLogger(__name__)


class GlobalSearchAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    PAGE_LIMIT = 6

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="search",
                type=str,
                description="Search keyword",
                required=False,
            )
        ],
        responses=GlobalSearchResponseSerializer,
    )
    def get(self, request, *args, **kwargs):
        keyword = request.query_params.get("search", "").strip()
        industry_filter = request.query_params.get("industry", None)
        location_filter = request.query_params.get("location", None)

        search_service = GlobalSearchService(
            search_term=keyword,
            industry_filter=industry_filter,
            location_filter=location_filter,
        )

        # --- Companies ---
        company_search = search_service.search_companies()
        total_companies = company_search.count()
        company_results = company_search[: self.PAGE_LIMIT].execute()

        # --- Jobs ---
        job_results = []
        total_jobs = 0
        try:
            user = self.request.user if self.request.user.is_authenticated else None
            # Build filters
            filters = None
            filter_dict = {}
            if industry_filter:
                filter_dict["industry"] = industry_filter
            if location_filter:
                filter_dict["location"] = location_filter
            if filter_dict:
                filters = json.dumps(filter_dict)
            
            total_jobs, job_results = JobRecommendationService.get_explore_job_search(
                self,
                user=user,
                query_string=keyword,
                filters=filters,
                ordering=None,
                page=1,
                page_size=self.PAGE_LIMIT,
            )
        except BadRequestException as e:
            logger.error(
                "Job recommendation service failed for keyword='%s': %s",
                keyword,
                e,
            )

        # --- People (Profiles) ---
        people_search = search_service.search_people_profiles()
        total_people = people_search.count()
        people_results = people_search[: self.PAGE_LIMIT].execute()
        company_map = {}
        profile_ids = [hit.meta.id for hit in people_results]
        if profile_ids:
            experiences = (
                WorkExperience.objects.filter(user_profile_id__in=profile_ids)
                .order_by("user_profile_id", "-is_currently_work", "-start_date")
                .values("user_profile_id", "company_name", "company__name")
            )
            for exp in experiences:
                # first row per profile wins: current job first, else latest by start_date
                name = exp["company__name"] or exp["company_name"]
                company_map.setdefault(str(exp["user_profile_id"]), name)
        # --- No results ---
        if not company_results and not job_results and not people_results:
            return Response(
                {
                    "success": False,
                    "message": "No results found for your search.",
                    "keyword": keyword,
                    "counts": {
                        "companies": 0,
                        "jobs": 0,
                        "people": 0,
                    },
                    "companies": [],
                    "jobs": [],
                    "people": [],
                },
                status=status.HTTP_200_OK,
            )

        # --- Serialize ---
        job_serializer = JobPostDocumentSerializer(job_results, many=True)
        company_serializer = CompanyDocumentSerializer(company_results, many=True)
        profile_serializer = ProfileDocumentSerializer(
            people_results,
            many=True,
            context={"company_map": company_map},
        )

        return Response(
            {
                "success": True,
                "message": "Search results retrieved successfully.",
                "keyword": keyword,
                "counts": {
                    "companies": total_companies,
                    "jobs": total_jobs,
                    "people": total_people,
                },
                "companies": company_serializer.data,
                "jobs": job_serializer.data,
                "people": profile_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="search",
            type=str,
            description="Search keyword",
            required=False,
        )
    ],
    responses=GlobalSearchResponseSerializer,
)
class PeopleProfileSearchView(BasePublicDocumentViewSet):
    document = ProfileDocument
    serializer_class = ProfileDocumentSerializer
    pagination_class = CustomPagination
    filter_backends = []

    def get_queryset(self):
        keyword = self.request.query_params.get("search", "").strip()

        if not keyword:
            return (
                self.document.search()
                .query("match_all")
                .filter(Q("term", profile_type=UserTypes.APPLICANT.value))
            )
        search_service = GlobalSearchService(
            search_term=keyword, user=self.request.user
        )

        return search_service.search_people_profiles()


class PeopleProfileDetailView(RetrieveModelMixin, GenericViewSet):
    queryset = Profile.objects.all()
    serializer_class = PeopleProfileDetailSerializer
    permission_classes = []
