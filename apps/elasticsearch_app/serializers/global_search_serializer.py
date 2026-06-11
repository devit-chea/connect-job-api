from django.utils import timezone as dtimezone
from rest_framework import serializers

from apps.auth_oauth.serializers.auth_serializer import ProfileSerializer
from apps.auth_oauth.serializers.profile_serializer import CompanySerializer
from apps.base.utils.file_management_util import FileURLService
from apps.elasticsearch_app.search.global_search_document import (
    CompanyDocument,
    ProfileDocument,
)
from apps.job_management_app.constants.job_post_types import JobPostStatusTypes
from apps.job_management_app.models.job_post_model import JobPostModel
from apps.job_management_app.serializers.job_post_serializer import (
    JobPostListSerializer,
)
from django_elasticsearch_dsl_drf.serializers import DocumentSerializer


class GlobalSearchCountSerializer(serializers.Serializer):
    companies = serializers.IntegerField()
    jobs = serializers.IntegerField()
    people = serializers.IntegerField()


class GlobalSearchResponseSerializer(serializers.Serializer):
    keyword = serializers.CharField()
    counts = GlobalSearchCountSerializer()
    companies = CompanySerializer(many=True)
    jobs = JobPostListSerializer(many=True)
    people = ProfileSerializer(many=True)


class ProfileDocumentSerializer(DocumentSerializer):
    profile_image_url = serializers.CharField(read_only=True)
    score = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    class Meta:
        document = ProfileDocument
        fields = [
            "id",
            "full_name",
            "first_name",
            "last_name",
            "job_title",
            "skills",
            "location_name",
            "current_position",
        ]
        read_only_fields = fields

    def get_score(self, obj):
        return round(getattr(obj.meta, "score", 0), 2)

    def get_company_name(self, obj):
        company_map = self.context.get("company_map", {})
        return company_map.get(str(obj.meta.id))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get("file_path")
        return data


class CompanyDocumentSerializer(DocumentSerializer):
    profile_image_url = serializers.CharField(read_only=True)
    
    class Meta:
        document = CompanyDocument
        fields = [
            "id",
            "name",
            "company_size",
            "description",
            "industry",
            "address",
            "jobs_open_count",
        ]
        read_only_fields = fields

    def get_jobs_open_count(self, obj):
        """
        Count jobs for this company.
        You can filter only active/open jobs if you have such field.
        """
        return JobPostModel.objects.filter(
            company_id=obj.id, 
            status=JobPostStatusTypes.ACTIVE.value,
            expire_date__gte=dtimezone.localdate(),
        ).count()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get("file_path")
        return data


class CompanyListDocumentSerializer(DocumentSerializer):
    profile_image_url = serializers.CharField(read_only=True)
    cover_image_url = serializers.CharField(read_only=True)
    job_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        document = CompanyDocument
        fields = [
            "id",
            "name",
            "phone_number",
            "email",
            "website",
            "is_active",
            "company_size",
            "description",
            "industry",
            "address",
            "about_me",
            "job_count",
        ]
        read_only_fields = fields

    def get_job_count(self, obj):
        """
        Count jobs for this company.
        You can filter only active/open jobs if you have such field.
        """
        return JobPostModel.objects.filter(
            company_id=obj.id,
            status=JobPostStatusTypes.ACTIVE.value,
            expire_date__gte=dtimezone.localdate(),
        ).count()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get("file_path")
        data["cover_image_url"] = (presentation.get("cover_image") or {}).get("file_path")
        return data


class CompanySearchDocumentSerializer(DocumentSerializer):
    logo_url = serializers.CharField(read_only=True)
    
    class Meta:
        document = CompanyDocument
        fields = [
            "id",
            "name",
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get("file_path")
        return data