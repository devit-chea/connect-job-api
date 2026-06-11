from drf_extra_fields.relations import PresentablePrimaryKeyRelatedField
from drf_writable_nested import WritableNestedModelSerializer
from rest_framework import serializers
from wdg_storage.base import WdgStorageMixin

from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.serializers.mobile_serializer import (
    MobileEducationSerializer,
    MobileLinkSerializer,
    MobileProfileLanguageSerializer,
    MobileSkillSerializer,
    MobileWorkExperienceSerializer,
)
from apps.auth_oauth.services.user_profile_service import UserProfileService
from apps.auth_oauth.utils.auth_util import get_full_name
from apps.base.fields.date_filed import DateField
from apps.base.mixins.permission_mixin import ensure_completed_profile
from apps.base.models.company_model import Company
from apps.base.models.geo_area_model import GeoArea
from apps.base.serializers.base_serializer import BaseSerializer
from apps.base.serializers.geo_area_serializer import GeoAreaInfoSerializer
from apps.base.utils.file_management_util import FileURLService


class ProfileApplicantUpdateSerializer(BaseSerializer):
    location = PresentablePrimaryKeyRelatedField(
        queryset=GeoArea.objects.all(),
        presentation_serializer=GeoAreaInfoSerializer,
        required=False,
        allow_null=True,
    )
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    phone_number = serializers.CharField()
    date_of_birth = DateField(allow_blank=True)
    location_name = serializers.CharField(required=True, allow_blank=False)
    gender = serializers.CharField(required=True, allow_blank=False, allow_null=False)

    class Meta:
        model = Profile
        fields = [
            "id",
            "first_name",
            "last_name",
            "gender",
            "date_of_birth",
            "phone_number",
            "email",
            "location",
            "location_name",
            "linkedin_profile",
            "website",
            "about_me",
            "profile_picture_id",
            "cover_picture_id"
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "profile_picture_id": {"read_only": True},
            "cover_picture_id": {"read_only": True},
        }

    def validate(self, attrs):
        request = self.context.get("request")
        # Exclude applicant and super_admin roles.
        ensure_completed_profile(request)
        return super().validate(attrs)

    def update(self, instance, validated_data):
        validated_data["full_name"] = get_full_name(
            validated_data.get("first_name", None),
            validated_data.get("last_name", None),
        )
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get("file_path")
        data["cover_image_url"] = (presentation.get("cover_image") or {}).get("file_path")
        return data


class CompanyProfileSerializer(BaseSerializer):
    pass


class CompanySerializer(BaseSerializer, WritableNestedModelSerializer):
    class Meta:
        model = Company
        fields = "__all__"


class ApplicantProfileRetrieveSerializer(BaseSerializer):
    location = PresentablePrimaryKeyRelatedField(
        queryset=GeoArea.objects.all(),
        presentation_serializer=GeoAreaInfoSerializer,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Profile
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "gender",
            "date_of_birth",
            "phone_number",
            "email",
            "location",
            "linkedin_profile",
            "website",
            "current_position",
            "about_me",
            "location_name",
            "department",
            "approval_reason",
            "current_address"
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get("file_path")
        data["cover_image_url"] = (presentation.get("cover_image") or {}).get("file_path")
        data["completion"] = UserProfileService.web_compute_profile_completion(profile=instance)
        return data


class ProfileImagesUpdateSerializer(BaseSerializer, WdgStorageMixin):
    """
    Update ONLY profile/cover image references.
    """
    profile_picture_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    cover_picture_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Profile
        fields = ["id", "profile_picture_id", "cover_picture_id", ]
        extra_kwargs = {"id": {"read_only": True}}

    def create(self, validated_data):
        instance = super().create(validated_data)
        files = [instance.profile_picture_id, instance.cover_picture_id]
        files_data = [
            {
                "file_id": file_id,
                "is_success": True,
                "instance": instance,
            }
            for file_id in files if file_id and str(file_id).strip()
        ]
        self.update_metadata(files_data)
        return instance

    def update(self, instance, validated_data):
        for key in ("profile_picture_id", "cover_picture_id"):
            if key in validated_data:
                setattr(instance, key, validated_data[key])
        instance.save(update_fields=["profile_picture_id", "cover_picture_id"])
        files = [instance.profile_picture_id, instance.cover_picture_id]
        files_data = [
            {
                "file_id": file_id,
                "is_success": True,
                "instance": instance,
            }
            for file_id in files if file_id and str(file_id).strip()
        ]
        self.update_metadata(files_data)
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get("file_path")
        data["cover_image_url"] = (presentation.get("cover_image") or {}).get("file_path")
        return data


class RecruiterProfessionalDetailSerializer(serializers.ModelSerializer):
    current_position = serializers.CharField(required=True, allow_blank=False)
    linkedin_profile = serializers.URLField(required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)
    
    class Meta:
        model = Profile
        fields = ["current_position", "department", "linkedin_profile", "website", ]


class PeopleProfileDetailSerializer(BaseSerializer):
    educations = MobileEducationSerializer(source="education_user_profile", many=True)
    work_experiences = MobileWorkExperienceSerializer(
        source="work_experience_user_profile", many=True
    )
    skills = MobileSkillSerializer(source="skill_user_profile", many=True)
    languages = MobileProfileLanguageSerializer(
        source="profile_language_user", many=True
    )
    links = MobileLinkSerializer(source="link_user_profile", many=True)

    location = PresentablePrimaryKeyRelatedField(
        queryset=GeoArea.objects.all(),
        presentation_serializer=GeoAreaInfoSerializer,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Profile
        fields = [
            "id",
            "about_me",
            "first_name",
            "last_name",
            "full_name",
            "current_position",
            "date_of_birth",
            "phone_number",
            "gender",
            "email",
            "educations",
            "work_experiences",
            "skills",
            "languages",
            "location",
            "location_name",
            "nationality",
            "links",
            "current_address",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get("file_path")
        data["cover_image_url"] = (presentation.get("cover_image") or {}).get("file_path")
        return data