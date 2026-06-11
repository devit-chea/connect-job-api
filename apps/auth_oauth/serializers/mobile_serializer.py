import logging
from drf_extra_fields.relations import PresentablePrimaryKeyRelatedField
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.auth_oauth.constants.auth_constants import LanguageLevels
from apps.auth_oauth.models.education_model import Education
from apps.auth_oauth.models.link_model import Link
from apps.auth_oauth.models.profile_language_model import ProfileLanguage, Language
from apps.auth_oauth.models.profile_model import ProfileDocumentModel, Profile
from apps.auth_oauth.models.skill_model import Skill
from apps.auth_oauth.models.work_experience_model import WorkExperience
from apps.auth_oauth.services.user_profile_service import UserProfileService
from apps.auth_oauth.utils.auth_util import get_active_profile_id
from apps.auth_oauth.utils.auth_util import set_active_profile, get_full_name
from apps.auth_oauth.utils.utils import group_educations, group_work_experiences, experience_item_duration
from apps.base.fields.date_filed import DateField
from apps.base.models.company_model import Company
from apps.base.models.geo_area_model import GeoArea
from apps.base.models.institution_model import Institution
from apps.base.serializers.base_serializer import BaseAndAuditSerializer
from apps.base.serializers.base_serializer import BaseSerializer
from apps.base.serializers.company_serializer import CompanyLookUpSerializer
from apps.base.serializers.geo_area_serializer import GeoAreaInfoSerializer
from apps.base.serializers.institution_serializer import InstitutionInfoSerializer
from apps.base.serializers.language_serializer import LanguageInfoSerializer
from apps.base.utils.file_management_util import FileURLService
from wdg_storage.base import get_file_url


logger = logging.getLogger(__name__)


class MobileEducationSerializer(BaseSerializer):
    institution = PresentablePrimaryKeyRelatedField(
        queryset=Institution.objects.all(),
        presentation_serializer=InstitutionInfoSerializer,
        required=False,
        allow_null=True,
    )
    location = PresentablePrimaryKeyRelatedField(
        queryset=GeoArea.objects.all(),
        presentation_serializer=GeoAreaInfoSerializer,
        required=False,
        allow_null=True,
    )
    start_date = DateField(allow_blank=True)
    is_currently_study = serializers.BooleanField(required=False, default=False)
    institution_name = serializers.CharField()
    duration = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Education
        fields = [
            "id",
            "institution_name",
            "institution",
            "start_date",
            "degree",
            "end_date",
            "study_field",
            "location",
            "location_name",
            "description",
            "is_currently_study",
            "user_profile",
            "duration",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "degree": {"required": True},
            "start_date": {"required": True},
            "user_profile": {"write_only": True},
        }

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

    def get_duration(self, obj):
        return experience_item_duration(obj.start_date, obj.end_date, obj.is_currently_study)


class MobileWorkExperienceSerializer(BaseSerializer):
    company = PresentablePrimaryKeyRelatedField(
        queryset=Company.objects.all(),
        presentation_serializer=CompanyLookUpSerializer,
        required=False,
        allow_null=True,
    )
    location = PresentablePrimaryKeyRelatedField(
        queryset=GeoArea.objects.all(),
        presentation_serializer=GeoAreaInfoSerializer,
        required=False,
        allow_null=True,
    )
    start_date = DateField(allow_blank=True)
    end_date = DateField(required=False, allow_null=True, )
    job_title = serializers.CharField()
    company_name = serializers.CharField()
    duration = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = WorkExperience
        fields = [
            "id",
            "job_title",
            "company_name",
            "location",
            "location_name",
            "company",
            "start_date",
            "end_date",
            "job_description",
            "is_currently_work",
            "user_profile",
            "duration"
        ]

        extra_kwargs = {
            "id": {"read_only": True},
            "start_date": {"required": True},
            "user_profile": {"write_only": True},
        }

    def validate(self, attrs):
        is_current = attrs.get("is_currently_work", False)
        end_date = attrs.get("end_date")
        if not is_current and not end_date:
            raise serializers.ValidationError({"end_date": "This field is required."})
        return attrs

    def to_internal_value(self, data):
        data = set_active_profile(self, data)
        if isinstance(data.get("end_date"), str) and not data["end_date"].strip():
            data["end_date"] = None
        return super().to_internal_value(data)

    def get_duration(self, obj):
        return experience_item_duration(obj.start_date, obj.end_date, obj.is_currently_work)


class MobileSkillSerializer(BaseSerializer):
    class Meta:
        model = Skill
        fields = [
            "id",
            "name",
            "description",
            "user_profile",
        ]

        extra_kwargs = {
            "id": {"read_only": True},
            "name": {"required": True},
            "user_profile": {"write_only": True},
        }

    def to_internal_value(self, data):
        data = set_active_profile(self, data)
        return super().to_internal_value(data)


class MobileProfileLanguageSerializer(BaseSerializer):
    language = PresentablePrimaryKeyRelatedField(
        queryset=Language.objects.all(),
        presentation_serializer=LanguageInfoSerializer,
        required=False,
        allow_null=True,
    )
    level = serializers.ChoiceField(choices=LanguageLevels.choices)
    language_name = serializers.CharField()

    class Meta:
        model = ProfileLanguage
        fields = [
            "id",
            "language",
            "level",
            "user_profile",
            "language_name"
        ]

        extra_kwargs = {
            "id": {"read_only": True},
            "user_profile": {"write_only": True},
        }

    def to_internal_value(self, data):
        data = set_active_profile(self, data)
        return super().to_internal_value(data)


class MobileLinkSerializer(BaseSerializer):
    class Meta:
        model = Link
        fields = ["id", "url", "title", "description", "user_profile"]

    def to_internal_value(self, data):
        data = set_active_profile(self, data)
        return super().to_internal_value(data)


class MobileUpdateCurrentProfileSerializer(
    BaseSerializer
):
    date_of_birth = DateField(allow_blank=True)
    first_name = serializers.CharField(required=True, allow_blank=False)
    last_name = serializers.CharField(required=True, allow_blank=False)
    current_position = serializers.CharField(required=True, allow_blank=False)
    phone_number = serializers.CharField(required=True, allow_blank=False)
    email = serializers.EmailField()
    location = PresentablePrimaryKeyRelatedField(
        queryset=GeoArea.objects.all(),
        presentation_serializer=GeoAreaInfoSerializer,
        required=False,
        allow_null=True,
    )
    location_name = serializers.CharField(required=True, allow_blank=False)
    gender = serializers.CharField(required=True, allow_blank=False, allow_null=False)

    class Meta:
        model = Profile
        fields = [
            "id",
            "about_me",
            "first_name",
            "last_name",
            "current_position",
            "date_of_birth",
            "phone_number",
            "current_address",
            "nationality",
            "email",
            "about_me",
            "gender",
            "location",
            "location_name",
            "cover_picture_id",
            "profile_picture_id"
        ]

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
        data["cover_image_url"] =  (presentation.get("cover_image") or {}).get("file_path")
        return data


class MobileCurrentProfileSerializer(BaseSerializer):
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
    has_cv = serializers.SerializerMethodField()
    cv_file_url = serializers.SerializerMethodField()
    has_preference = serializers.SerializerMethodField()

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
            "total_experience_years",
            "has_cv",
            "has_preference",
            "job_preference",
            "profile_picture_id",
            "cover_picture_id",
            "cv_file_url",
        ]

    def get_has_cv(self, obj):
        cv_exists = obj.documents.filter(
            document_type=ProfileDocumentModel.DocumentType.CV,
            status=ProfileDocumentModel.Status.ACTIVE
        ).exists()

        return cv_exists

    def get_cv_file_url(self, obj):
        cv_document = obj.documents.filter(
            document_type=ProfileDocumentModel.DocumentType.CV,
            status=ProfileDocumentModel.Status.ACTIVE
        ).first()
        
        if cv_document and cv_document.document_id:
            try:
                return get_file_url(file_id=cv_document.document_id)
            except (ValueError, FileNotFoundError, Exception) as e:
                logger.error(
                    f"Failed to generate CV file URL for profile {obj.id}, file ID {cv_document.document_id}: {e}"
                )
                return None
        return None 
        
    def get_has_preference(self, obj):
        return bool(obj.job_preference)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get("file_path")
        data["cover_image_url"] = (presentation.get("cover_image") or {}).get("file_path")
        data["completion"] = UserProfileService.mb_compute_profile_completion(data)

        data["work_experiences"] = group_work_experiences(data.get("work_experiences"))
        data["educations"] = group_educations(data.get("educations"))
        
        job_pref = data.get("job_preference")
        if not job_pref:
            data["job_preference"] = None
        else:
            if isinstance(job_pref, dict) and not any(job_pref.values()):
                data["job_preference"] = None
                
        return data


class MobileProfileDocumentSerializer(BaseAndAuditSerializer):
    profile = serializers.PrimaryKeyRelatedField(
        queryset=Profile.objects.all(), required=False, allow_null=True,
    )
    document_id = serializers.CharField()
    inject_company_id = False
    document_type = serializers.ChoiceField(choices=ProfileDocumentModel.DocumentType.choices)

    class Meta:
        model = ProfileDocumentModel
        fields = [
            "id",
            "profile",
            "document_id",
            "document_type",
            "is_default",
            "status",
        ]

    def to_internal_value(self, data):
        active_profile_id, _ = get_active_profile_id(self.context.get("request", None))
        data["profile"] = active_profile_id
        return super().to_internal_value(data)

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)


class MobileProfileDocumentLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileDocumentModel
        fields = ["document_id", "document_type"]
        file_mapping_ref_type = "profiledocumentmodel"
