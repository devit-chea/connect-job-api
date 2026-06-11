from datetime import datetime
from django.db.models import Q
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from drf_writable_nested.serializers import WritableNestedModelSerializer
from apps.auth_oauth.constants.auth_constants import (
    DefaultRole,
    ProfileStatus,
    UserTypes,
)
from apps.auth_oauth.models.education_model import Education
from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.models.skill_model import Skill
from apps.auth_oauth.models.profile_language_model import ProfileLanguage
from apps.auth_oauth.models.work_experience_model import WorkExperience
from apps.auth_oauth.services.user_company_profile_service import (
    UserCompanyProfileService,
)
from apps.auth_oauth.services.user_service import UserService
from apps.auth_oauth.utils.auth_util import (
    get_active_profile_id,
    get_default_role,
    get_full_name,
)
from apps.auth_oauth.utils.utils import normalize_date_string
from apps.base.constants.base_constants import Status
from apps.base.models.company_model import Company
from apps.base.models.geo_area_model import GeoArea
from apps.base.models.institution_model import Institution
from apps.base.models.language_model import Language
from apps.base.serializers.base_serializer import BaseCompanySerializer
from apps.base.serializers.geo_area_serializer import GeoAreaInfoSerializer
from apps.base.serializers.institution_serializer import InstitutionInfoSerializer
from apps.base.utils.base_util import get_default_company
from drf_extra_fields.relations import PresentablePrimaryKeyRelatedField


class NullableDateFormatMixin:
    """
    Return None when date format is invalid.
    """

    DATE_FORMAT = "%Y-%m-%d"

    def validate_nullable_date(self, value):
        if not value:
            return None

        try:
            datetime.strptime(value, self.DATE_FORMAT)
            return value
        except (ValueError, TypeError):
            return None


class LanguageLookupField(serializers.Field):
    """
    A custom field to look up a Language instance by name (case-insensitive).
    Returns the Language instance if found, or None if not found.
    The original input string is stored temporarily in the serializer's context.
    """

    def to_internal_value(self, data):
        if not data:
            return None

        # Store the original string input for the free-text field (language_name)
        # This is a common pattern when a field dictates data in another field.
        self.parent.language_input = data

        try:
            return Language.objects.get(Q(name__iexact=data) | Q(code__iexact=data))
        except Language.DoesNotExist:
            return None
        except Language.MultipleObjectsReturned:
            raise serializers.ValidationError(
                f"Multiple languages found for '{data}'. Contact administrator."
            )

    def to_representation(self, value):
        if value and isinstance(value, Language):
            return value.name
        return self.parent.instance.language_name if self.parent.instance else None


class ProfileLanguageSerializer(WritableNestedModelSerializer):
    """Serializer for the ProfileLanguage model."""

    language_input_name = LanguageLookupField(write_only=True, required=False)
    language = serializers.PrimaryKeyRelatedField(read_only=True)
    level = serializers.CharField(
        required=False,
        write_only=True,
        allow_null=True,
        allow_blank=True,
        default=None,
    )

    class Meta:
        model = ProfileLanguage
        fields = [
            "id",
            "language_input_name",
            "language",
            "language_name",
            "level",
            "user_profile",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
        }

    def validate_level(self, value):
        # Convert empty string to null
        if value == "":
            return None
        return value

    def create(self, validated_data):
        # Set level to null if not provided
        validated_data.setdefault("level", None)

        language_instance = validated_data.pop("language_input_name")

        if language_instance:
            validated_data["language"] = language_instance
            validated_data["language_name"] = language_instance.name
        else:
            validated_data["language"] = None
            validated_data["language_name"] = self.language_input

        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Set level to null if empty string
        if validated_data.get("level") == "":
            validated_data["level"] = None

        language_instance = validated_data.pop("language_input_name", None)

        if language_instance:
            validated_data["language"] = language_instance
            validated_data["language_name"] = language_instance.name
        elif language_instance is None and "language_input_name" in validated_data:
            validated_data["language"] = None
            validated_data["language_name"] = self.language_input

        return super().update(instance, validated_data)


class LanguageSerializer(WritableNestedModelSerializer):
    """Serializer for the Skill model."""

    class Meta:
        model = ProfileLanguage
        fields = ["id", "language", "language_name", "level"]


class SkillSerializer(WritableNestedModelSerializer):
    """Serializer for the Skill model."""

    class Meta:
        model = Skill
        fields = ["id", "name", "description"]


class EducationSerializer(WritableNestedModelSerializer, NullableDateFormatMixin):
    """Serializer for the Education model."""

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
    start_date = serializers.CharField(required=False, allow_null=True)
    end_date = serializers.CharField(required=False, allow_null=True)
    is_currently_study = serializers.BooleanField(required=False, default=False)
    institution_name = serializers.CharField()

    class Meta:
        model = Education
        fields = [
            "id",
            "institution_name",
            "institution",
            "degree",
            "start_date",
            "end_date",
            "location",
            "location_name",
            "description",
            "study_field",
            "is_currently_study",
        ]

        extra_kwargs = {
            "id": {"read_only": True},
        }

    def validate_start_date(self, value):
        return self.validate_nullable_date(value)

    def validate_end_date(self, value):
        return self.validate_nullable_date(value)


class WorkExperienceSerializer(WritableNestedModelSerializer, NullableDateFormatMixin):
    """Serializer for the WorkExperience model."""

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
    start_date = serializers.CharField(required=False, allow_null=True)
    end_date = serializers.CharField(required=False, allow_null=True)
    job_title = serializers.CharField()
    company_name = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, write_only=True
    )

    class Meta:
        model = WorkExperience
        fields = [
            "id",
            "job_title",
            "company_name",
            "company",
            "location",
            "location_name",
            "start_date",
            "end_date",
            "job_description",
            "is_currently_work",
        ]

        extra_kwargs = {
            "id": {"read_only": True},
        }

    def validate_start_date(self, value):
        return self.validate_nullable_date(value)

    def validate_end_date(self, value):
        return self.validate_nullable_date(value)


# --- Main Profile Serializer ---
class ProfileCVScanSerializer(WritableNestedModelSerializer):
    """
    Main serializer for the Profile model, including nested writable
    serializers for related Skills, Education, and Work Experience.
    """

    first_name = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, write_only=True
    )
    last_name = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, write_only=True
    )
    # Use related_name from the ForeignKey fields to link the nested serializers
    skill_user_profile = SkillSerializer(many=True, required=False)
    education_user_profile = EducationSerializer(many=True, required=False)
    work_experience_user_profile = WorkExperienceSerializer(many=True, required=False)
    profile_language_user = ProfileLanguageSerializer(many=True, required=False)
    date_of_birth = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )

    class Meta:
        model = Profile
        fields = [
            "id",
            "user",
            "profile_picture_id",
            "cover_picture_id",
            "first_name",
            "last_name",
            "full_name",
            "gender",
            "date_of_birth",
            "phone_number",
            "email",
            "location",
            "location_name",
            "linkedin_profile",
            "website",
            "current_position",
            "current_address",
            "nationality",
            "company",
            "job_preference",
            "status",
            "is_active",
            "submitted_date",
            "approval_reason",
            "profile_type",
            "about_me",
            "request_type",
            "skills",  # ArrayField
            "skill_user_profile",  # Nested Skills
            "profile_language_user",  # Nested Language
            "education_user_profile",  # Nested Education
            "work_experience_user_profile",  # Nested Work Experience
        ]
        read_only_fields = ("submitted_date",)
        extra_kwargs = {
            "id": {"read_only": True},
            "user": {"read_only": True},
        }

    # ------------------------------------------------------------------
    # Inject user & company before validation
    # ------------------------------------------------------------------
    def to_internal_value(self, data):
        request = self.context.get("request")
        user_instance = getattr(request, "user", None)

        if not user_instance or not user_instance.is_authenticated:
            raise ValidationError({"user": "Authentication required."})

        company_instance = get_default_company()
        if not company_instance:
            raise ValidationError({"company": "Default company not found."})

        data["create_uid"] = user_instance.pk
        return super().to_internal_value(data)

    # ------------------------------------------------------------------
    # MASTER create() – decides CREATE vs UPDATE
    # ------------------------------------------------------------------
    def create(self, validated_data):
        request = self.context.get("request")
        profile_id = request.profile_id

        # If profile_id present → UPDATE
        if profile_id:
            try:
                instance = Profile.objects.get(pk=profile_id, user=request.user)
            except Profile.DoesNotExist:
                raise ValidationError({"profile_id": "Profile not found."})

            return self.update_existing_profile(instance, validated_data)

        # Otherwise → CREATE new profile
        return self.create_new_profile(validated_data)

    # ------------------------------------------------------------------
    # CREATE NEW PROFILE (Atomic)
    # ------------------------------------------------------------------
    def create_new_profile(self, validated_data):
        request = self.context.get("request")
        user_id = request.user.pk
        default_company = get_default_company()

        with transaction.atomic():
            validated_data["user_id"] = user_id
            validated_data["profile_type"] = UserTypes.APPLICANT.value
            validated_data["company"] = default_company
            validated_data["status"] = Status.COMPLETE
            validated_data["email"] = request.user.email
            validated_data["full_name"] = get_full_name(
                validated_data.get("first_name"),
                validated_data.get("last_name"),
            )

            # Create Profile + nested models
            instance = super().create(validated_data)

            # Create/update UserCompanyProfile
            data = {
                "user": user_id,
                "status": ProfileStatus.ACTIVE,
                "type": UserTypes.APPLICANT,
                "company": default_company.pk,
                "profile": instance.pk,
            }

            ucp_instance = UserCompanyProfileService().create_or_update(
                data,
                user=user_id,
                company=default_company.pk,
                profile_type=UserTypes.APPLICANT,
            )

            # Assign default role
            default_role = get_default_role(code=DefaultRole.APPLICANT_ROLE)
            _, user_company_profile_id = get_active_profile_id(request)
            ucp_instance.roles.set(default_role)

            # Update relations in UCP
            UserCompanyProfileService().update_profile_relation(
                profile_id=instance.pk,
                company_id=default_company,
                user_company_profile_id=user_company_profile_id,
            )

            # Update User data
            UserService().update_fname_and_lname(user_id, validated_data)

        return instance

    # ------------------------------------------------------------------
    # UPDATE EXISTING PROFILE (Atomic)
    # ------------------------------------------------------------------
    def update_existing_profile(self, instance, validated_data):
        request = self.context.get("request")
        default_company = get_default_company()

        with transaction.atomic():
            # Update nested + main profile
            instance = super().update(instance, validated_data)

            if getattr(request, "user_type", None):
                instance.status = Status.COMPLETE
                instance.profile_type = UserTypes.APPLICANT

            # Update full name
            instance.full_name = get_full_name(instance.first_name, instance.last_name)
            instance.save()

            # Update user model fname / lname
            UserService().update_fname_and_lname(request.user.pk, validated_data)

            # Update relations in UCP
            _, user_company_profile_id = get_active_profile_id(request)
            UserCompanyProfileService().update_profile_relation(
                profile_id=instance.pk,
                company_id=default_company,
                user_company_profile_id=user_company_profile_id,
            )
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        dob = instance.date_of_birth

        if dob:
            data["date_of_birth"] = normalize_date_string(dob)

        return data


class FileUploadSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)

    ALLOWED_MIME_TYPES = {
        # PDF
        "application/pdf",
        # Images
        "image/jpeg",
        "image/png",
        "image/jpg",
        "image/webp",
        "image/gif",
        "image/heic",
        "image/heif",
        # Microsoft Word
        "application/msword",  # .doc
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    }

    ALLOWED_EXTENSIONS = {
        # PDF
        "pdf",
        # Images
        "jpg",
        "jpeg",
        "png",
        "webp",
        "gif",
        "heic",
        "heif",
        # Microsoft Word
        "doc",
        "docx",
    }

    def validate_file(self, value):
        # Validate MIME type
        if value.content_type not in self.ALLOWED_MIME_TYPES:
            raise ValidationError(f"Unsupported file type '{value.content_type}'.")

        # Validate extension
        if "." not in value.name:
            raise ValidationError("File must have a valid extension.")

        extension = value.name.rsplit(".", 1)[1].lower()

        if extension not in self.ALLOWED_EXTENSIONS:
            raise ValidationError(f"Unsupported file extension '.{extension}'.")

        return value
