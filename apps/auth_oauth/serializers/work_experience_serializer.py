from drf_extra_fields.relations import PresentablePrimaryKeyRelatedField
from rest_framework import serializers

from apps.auth_oauth.models.work_experience_model import WorkExperience
from apps.auth_oauth.utils.auth_util import set_active_profile
from apps.auth_oauth.utils.utils import experience_item_duration
from apps.base.fields.date_filed import DateField
from apps.base.models.company_model import Company
from apps.base.models.geo_area_model import GeoArea
from apps.base.serializers.base_serializer import BaseSerializer, BaseCompanySerializer
from apps.base.serializers.geo_area_serializer import GeoAreaInfoSerializer


class WorkExperiencesProfileSerializer(BaseSerializer):
    location = PresentablePrimaryKeyRelatedField(
        queryset=GeoArea.objects.all(),
        presentation_serializer=GeoAreaInfoSerializer,
        required=False,
        allow_null=True,
    )
    company = PresentablePrimaryKeyRelatedField(
        queryset=Company.objects.all(),
        presentation_serializer=BaseCompanySerializer,
        required=False,
        allow_null=True,
    )
    start_date = DateField(required=True)
    job_title = serializers.CharField()
    end_date = DateField(required=False, allow_null=True, )
    company_name = serializers.CharField()
    duration = serializers.SerializerMethodField(read_only=True)
    class Meta:
        model = WorkExperience
        fields = [
            "id",
            "user_profile",
            "company_name",
            "location",
            "location_name",
            "company",
            "job_title",
            "job_description",
            "start_date",
            "end_date",
            "is_currently_work",
            "duration"
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "start_date": {"required": True},
        }

    def to_internal_value(self, data):
        data = set_active_profile(self, data)

        if isinstance(data.get("end_date"), str) and not data["end_date"].strip():
            data["end_date"] = None
        return super().to_internal_value(data)

    def validate(self, attrs):
        is_current = attrs.get("is_currently_work", False)
        end_date = attrs.get("end_date")
        start_date = attrs.get("start_date")
        
        if not is_current and not end_date:
            raise serializers.ValidationError({"end_date": "This field is required."})
        if end_date and start_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "End date cannot be a past date."})
    
        return attrs

    def get_duration(self, obj):
        return experience_item_duration(obj.start_date, obj.end_date, obj.is_currently_work)