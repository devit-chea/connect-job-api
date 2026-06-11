from copy import deepcopy

from django_elasticsearch_dsl_drf.filter_backends import (
    OrderingFilterBackend,
    DefaultOrderingFilterBackend,
)

from apps.base.views.base_document_view_set import BaseDocumentViewSet
from apps.core.pagination import CustomPagination
from apps.elasticsearch_app.constants.es_constants import ORDERING_FIELDS
from apps.elasticsearch_app.mixins.es_job_post_mixins import JobPostImageContextMixin
from apps.elasticsearch_app.models.job_post_document import JobPostDocument
from apps.elasticsearch_app.serializers.job_post_document_serializer import (
    JobPostDocumentSerializer,
)
from apps.elasticsearch_app.services.job_recommendation_service import (
    JobRecommendationService,
)


class ElasticSearchRecommendJobView(JobPostImageContextMixin, BaseDocumentViewSet):
    document = JobPostDocument
    serializer_class = JobPostDocumentSerializer
    pagination_class = CustomPagination

    filter_backends = [
        OrderingFilterBackend,
        DefaultOrderingFilterBackend,
    ]
    ordering_fields = deepcopy(ORDERING_FIELDS)

    def get_queryset(self):
        user = self.request.user
        query_string = self.request.query_params.get("search", None)
        page = int(self.request.query_params.get("page", 1))
        page_size = int(self.request.query_params.get("page_size", 10))
        ordering = self.request.query_params.get("ordering", None)
        filters = self.request.query_params.get("filters", None)

        return JobRecommendationService.get_explore_job(
            self, user, query_string, filters, ordering, page, page_size
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        context = {**self.get_serializer_context(), **self._build_image_context(page)}
        ser = self.get_serializer(page, many=True, context=context)
        data = ser.data  # list[dict]

        user = request.user if request.user.is_authenticated else None
        enriched = JobRecommendationService.attach_user_states(user, data)

        return self.get_paginated_response(enriched)
