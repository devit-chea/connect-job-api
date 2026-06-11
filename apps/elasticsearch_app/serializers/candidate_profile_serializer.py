from django_elasticsearch_dsl_drf.serializers import DocumentSerializer

from apps.elasticsearch_app.models.candidate_profile_document import CandidateProfileDocument


class CandidateProfileSerializer(DocumentSerializer):
    class Meta:
        document = CandidateProfileDocument
        fields = '__all__'
