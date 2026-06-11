from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from elasticsearch_dsl import Search
from drf_spectacular.utils import extend_schema

from apps.elasticsearch_app.queries.compay_builder_query import CompanySearchFilters
from apps.elasticsearch_app.search.search_suggestion_document import (
    CompanyDocument,
    JobDocument,
)
from apps.elasticsearch_app.serializers.global_search_serializer import CompanySearchDocumentSerializer
from apps.elasticsearch_app.serializers.search_suggestion_serializer import (
    SearchSuggestionQuerySerializer,
)
from apps.elasticsearch_app.services.global_search_service import GlobalSearchService


class GlobalSuggestionAPIView(APIView):
    """
    Returns autocomplete suggestions for jobs and companies
    """

    authentication_classes = []
    permission_classes = []

    @extend_schema(parameters=[SearchSuggestionQuerySerializer], responses={200: dict})
    def get(self, request, *args, **kwargs):
        serializer = SearchSuggestionQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        query = validated_data.get("search", "")
        if not query:
            return Response({"suggested_keywords": [], "companies": []})

        now = timezone.now()
        # JOB suggestions
        job_search = (
            Search(index=JobDocument._index._name)
            .query(
                "multi_match",
                query=query,
                fields=[
                    "title.as_you_type",
                    "title.edge_ngram_analyzer",
                ],
                type="bool_prefix",
            )
            .filter("range", expire_date={"gte": now})
            .source(["title"])
            .extra(size=5)
        )
        job_res = job_search.execute()
        job_suggestions = [hit.title for hit in job_res[:5]]

        # COMPANY suggestions
        search_service = GlobalSearchService(
            search_term=query,
        )
        company_search = search_service.search_companies()
        company_results = company_search[:5].execute()
        company_serializer = CompanySearchDocumentSerializer(company_results, many=True)

        return Response(
            {"suggested_keywords": job_suggestions, "companies": company_serializer.data}
        )
