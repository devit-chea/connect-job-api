from django_elasticsearch_dsl_drf.viewsets import DocumentViewSet
from rest_framework.permissions import AllowAny

from apps.core.pagination import CustomPagination
from apps.elasticsearch_app.models.candidate_profile_document import CandidateProfileDocument
from apps.elasticsearch_app.serializers.candidate_profile_serializer import CandidateProfileSerializer


class CandidateProfileView(DocumentViewSet):
    permission_classes = [AllowAny]
    document = CandidateProfileDocument
    serializer_class = CandidateProfileSerializer
    pagination_class = CustomPagination
