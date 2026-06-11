from drf_extra_fields.relations import PresentablePrimaryKeyRelatedField
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.auth_oauth.models.education_model import Education
from apps.auth_oauth.utils.auth_util import set_active_profile
from apps.auth_oauth.utils.utils import experience_item_duration
from apps.base.fields.date_filed import DateField
from apps.base.models.geo_area_model import GeoArea
from apps.base.models.institution_model import Institution
from apps.base.serializers.base_serializer import BaseSerializer
from apps.base.serializers.geo_area_serializer import GeoAreaInfoSerializer
from apps.base.serializers.institution_serializer import InstitutionInfoSerializer


class EducationsProfileSerializer(BaseSerializer):
    location = PresentablePrimaryKeyRelatedField(
        queryset=GeoArea.objects.all(),
        presentation_serializer=GeoAreaInfoSerializer,
        required=False,
        allow_null=True,
    )
    institution = PresentablePrimaryKeyRelatedField(
        queryset=Institution.objects.all(),
        presentation_serializer=InstitutionInfoSerializer,
        required=False,
        allow_null=True,
    )
    start_date = DateField(required=True, allow_blank=True)
    end_date = DateField(required=False, allow_null=True, )
    is_currently_study = serializers.BooleanField(required=False, default=False)
    institution_name = serializers.CharField()
    duration = serializers.SerializerMethodField(read_only=True)
    degree = serializers.CharField(required=True, allow_blank=False, allow_null=False)

    class Meta:
        model = Education
        fields = [
            "id",
            "user_profile",
            "institution_name",
            "institution",
            "degree",
            "start_date",
            "end_date",
            "location",
            "location_name",
            "study_field",
            "description",
            "is_currently_study",
            "duration",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "start_date": {"required": True},
            "study_field": {"required": True},
        }

    def get_duration(self, obj):
        return experience_item_duration(obj.start_date, obj.end_date, obj.is_currently_study)

    def to_internal_value(self, data):
        data = set_active_profile(self, data)
        if isinstance(data.get("end_date"), str) and not data["end_date"].strip():
            data["end_date"] = None
        return super().to_internal_value(data)

    def validate(self, attrs):
        is_current = attrs.get("is_currently_study", getattr(self.instance, "is_currently_study", False))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if is_current:
            attrs["end_date"] = None
        elif end is None:
            raise ValidationError({"end_date": "This field is required."})
        return attrs
