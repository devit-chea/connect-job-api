from rest_framework import serializers
from django_elasticsearch_dsl_drf.serializers import DocumentSerializer

from apps.elasticsearch_app.search.search_suggestion_document import (
    CompanyDocument,
    JobDocument,
)

class SearchSuggestionQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True)

class JobDocumentSerializer(DocumentSerializer):
    class Meta:
        document = JobDocument
        fields = ("id", "title", "skills")


class CompanyDocumentSerializer(DocumentSerializer):
    class Meta:
        document = CompanyDocument
        fields = ("id", "name", "logo_url")
