import re
from datetime import datetime
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from drf_extra_fields.relations import PresentablePrimaryKeyRelatedField
from rest_framework import serializers

from apps.auth_oauth.constants.auth_constants import (
    UserTypes,
    ApplicantBecomeRecruiterStep,
    RequestType,
    UserState,
    UserStatus,
    DefaultRole,
)
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.serializers.recruiter_serializer import RecruiterSignupSerializer
from apps.auth_oauth.services.user_company_profile_service import (
    UserCompanyProfileService,
)
from apps.auth_oauth.services.user_profile_service import UserProfileService
from apps.auth_oauth.services.user_service import UserService
from apps.auth_oauth.utils.auth_util import (
    get_full_name,
    get_active_profile_id,
    get_default_role,
)
from apps.base.constants.base_constants import Status
from apps.base.fields.date_filed import DateField
from apps.base.models.company_model import Company
from apps.base.models.country_model import Country
from apps.base.models.geo_area_model import GeoArea
from apps.base.serializers.base_serializer import BaseSerializer
from apps.base.serializers.country_serializer import CountryInfoSerializer
from apps.base.serializers.geo_area_serializer import GeoAreaInfoSerializer
from apps.base.services.company_service import CompanyService
from apps.base.utils.base_util import get_default_company
from apps.core.exceptions.base_exceptions import BadRequestException


class ApplicantToRecruiterSerializer(BaseSerializer):

    def __init__(self, instance=None, data=..., profile_type=None, **kwargs):
        self.profile_type = profile_type
        super().__init__(instance, data, **kwargs)

    step = serializers.CharField(write_only=True)

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "industry",
            "found_date",
            "company_size",
            "profile_picture_id",
            "address",
            "city",
            "country",
            "postal_code",
            "phone_number",
            "email",
            "linkedin_email",
            "website",
            "about_me",
            "is_agree_policy",
            "step",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
        }

    def validate_phone_number(self, value):
        """
        Validates Cambodian phone numbers.
        Formats: 012345678, 0123456789, +85512345678, etc.
        """
        # Remove spaces, dashes, or parentheses if they exist
        clean_number = re.sub(r'[\s\-()]+', '', value)

        # Regex explanation:
        # ^(\+855|0) -> Starts with +855 or 0
        # [1-9]      -> The next digit (operator code) isn't 0
        # \d{7,8}$   -> Followed by 7 or 8 more digits (Total 9 or 10 digits)
        kh_phone_regex = r'^(\+855|0)[1-9]\d{7,8}$'

        if not re.match(kh_phone_regex, clean_number):
            raise serializers.ValidationError(
                _("Please enter a valid phone number (e.g., 012345678 or +85512345678).")
            )

        return clean_number
    
    def to_internal_value(self, data):
        step = data.get("step", None)
        if step == ApplicantBecomeRecruiterStep.ABR1:
            self.fields["name"] = serializers.CharField()
            self.fields["industry"] = serializers.CharField()
            self.fields["found_date"] = serializers.CharField()

        elif step == ApplicantBecomeRecruiterStep.ABR2:
            self.fields["address"] = serializers.CharField()
            self.fields["city"] = PresentablePrimaryKeyRelatedField(
                queryset=GeoArea.objects.all(),
                presentation_serializer=GeoAreaInfoSerializer,
            )
            self.fields["country"] = PresentablePrimaryKeyRelatedField(
                queryset=Country.objects.all(),
                presentation_serializer=CountryInfoSerializer,
            )
            self.fields["phone_number"] = serializers.CharField()
            self.fields["email"] = serializers.CharField()
            self.fields["about_me"] = serializers.CharField()
        else:
            raise BadRequestException("invalid step")

        return super().to_internal_value(data)

    def create(self, validated_data):
        request = self.context.get("request", None)
        step = validated_data.pop("step", None)
        files = validated_data.pop("files", None)
        instance = None
        user = request.user if request and request.user else None
        user_id = self.safe_get(user, "id")

        # if step not final not save data
        with transaction.atomic():
            is_existed, existed_instance = CompanyService().is_existed(
                data={"name": validated_data.get("name", None)}
            )
            validated_data["status"] = Status.PENDING
            validated_data["is_active"] = False
            validated_data["is_existed"] = is_existed
            validated_data["existed_company"] = existed_instance
            instance = super().create(validated_data)
            active_profile_id, _ = get_active_profile_id(request)
            profile_type_applicant = UserProfileService().get_by_id(
                profile_id=active_profile_id
            )
            profile_data = {
                "user": user_id,
                "first_name": self.safe_get(profile_type_applicant, "first_name"),
                "last_name": self.safe_get(profile_type_applicant, "last_name"),
                "date_of_birth": self.safe_get(profile_type_applicant, "date_of_birth"),
                "gender": self.safe_get(profile_type_applicant, "gender"),
                "phone_number": self.safe_get(profile_type_applicant, "phone_number"),
                "current_position": self.safe_get(
                    profile_type_applicant, "current_position"
                ),
                "company": (
                    instance.pk
                    if instance and step == ApplicantBecomeRecruiterStep.ABR2
                    else None
                ),
                "status": Status.PENDING,
                "profile_type": self.profile_type,
                "request_type": RequestType.BECOME_RECRUITER,
                "submitted_date": datetime.now(),
            }
            profile = UserProfileService().create(profile_data)
            data = {
                "user": user.pk if user else None,
                "status": UserStatus.ACTIVE,
                "type": self.profile_type,
                "company": instance.pk if instance else None,
                "profile": profile.pk if profile else None,
                "state": UserState.COMPLETE_SETUP_PROFILE,
            }
            default_role = get_default_role(code=DefaultRole.RECRUITER_ROLE)
            user_company_instance = UserCompanyProfileService.create(data)
            if user_company_instance:
                user_company_instance.roles.set(default_role)

            if step != ApplicantBecomeRecruiterStep.ABR2:
                transaction.set_rollback(True)

        return instance

    def safe_get(self, attr, key):
        return getattr(attr, key, None) if attr else None


class ApplicantSignupSerializer(RecruiterSignupSerializer):
    pass


class ExpectedSalary(serializers.Serializer):
    min = serializers.FloatField(required=False)
    max = serializers.FloatField(required=False)


class JobPreferenceSerializer(serializers.Serializer):
    position_titles = serializers.ListField(
        child=serializers.CharField(required=False, allow_null=True),
        required=False,
        allow_null=True,
    )
    job_location = serializers.ListField(
        child=serializers.CharField(required=False, allow_null=True),
        required=False,
        allow_null=True,
    )
    employment_type = serializers.ListField(
        child=serializers.CharField(required=False, allow_null=True),
        allow_empty=True,
        required=False,
        allow_null=True,
    )
    work_type = serializers.ListField(
        child=serializers.CharField(required=False, allow_null=True),
        allow_empty=True,
        required=False,
        allow_null=True,
    )
    excepted_salary = ExpectedSalary(required=False)

    def validate(self, attrs):
        pos = attrs.get("position_titles") or []
        work = attrs.get("work_type") or []
        emp = attrs.get("employment_type") or []

        # If user fills ANY field -> require all 3
        if pos or work or emp:
            errors = {}

            if not pos:
                errors["position_titles"] = "This field is required when saving job preference."
            if not work:
                errors["work_type"] = "This field is required when saving job preference."
            if not emp:
                errors["employment_type"] = "This field is required when saving job preference."

            if errors:
                raise serializers.ValidationError(errors)

        # If all empty -> allow save
        return attrs


class UserInfoSerializer(BaseSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]
        ref_name = "applicant_user_info"
        ref_name = "applicant_user_info"


class ApplicantProfileSignupSerializer(BaseSerializer):
    user = PresentablePrimaryKeyRelatedField(
        queryset=User.objects.all(),
        presentation_serializer=UserInfoSerializer,
        required=False,
        allow_null=True,
    )
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    date_of_birth = DateField(allow_null=True, allow_blank=True)
    phone_number = serializers.CharField()
    current_position = serializers.CharField()
    gender = serializers.CharField()
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = Profile
        fields = [
            "id",
            "first_name",
            "last_name",
            "gender",
            "date_of_birth",
            "phone_number",
            "current_position",
            "user",
            "cover_picture_id",
            "profile_picture_id",
            "email",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "user": {"read_only": True},
        }

    def validate(self, attrs):
        request = self.context.get("request")
        _, ucp_id = get_active_profile_id(request)
        ucp = UserCompanyProfileService().get_by_id(ucp_id)
        if not ucp:
            raise serializers.ValidationError("Active profile not found.")
        if ucp.type != UserTypes.APPLICANT:
            raise serializers.ValidationError("This endpoint is only for applicant setup.")
        if getattr(ucp, "state", None) != "pending_setup_profile":
            raise serializers.ValidationError("You have already completed profile setup.")
        return attrs

    @transaction.atomic()
    def create(self, validated_data):
        request = self.context.get("request", None)
        user_id = request.user.pk if request and request.user else None
        default_company = get_default_company()
        validated_data["user_id"] = user_id
        validated_data["profile_type"] = UserTypes.APPLICANT.value
        validated_data["company"] = default_company
        validated_data["status"] = Status.COMPLETE
        validated_data["full_name"] = get_full_name(
            validated_data.get("first_name", None),
            validated_data.get("last_name", None),
        )
        _, user_company_profile_id = get_active_profile_id(request)
        ucp_service = UserCompanyProfileService()
        current_ucp = ucp_service.get_by_id(user_company_profile_id)
        existing_profile_id = getattr(current_ucp, "profile_id", None)

        if existing_profile_id:
            try:
                instance = Profile.objects.get(pk=existing_profile_id)
                update_fields = [
                    "first_name", "last_name", "date_of_birth", "phone_number",
                    "current_position", "gender", "full_name", "status", "profile_picture_id", "email"
                ]
                if instance.status == Status.COMPLETE:
                    raise serializers.ValidationError(
                        "Profile is already complete please use update profile.")
                for field in update_fields:
                    if field in validated_data:
                        setattr(instance, field, validated_data[field])
                instance.save()
                ucp_service.update_profile_relation(
                    profile_id=instance.pk,
                    company_id=default_company,
                    user_company_profile_id=user_company_profile_id,
                )
            except Profile.DoesNotExist:
                instance = super().create(validated_data)
                # Need to link the newly created profile to the UCP
                ucp_service.update_profile_relation(
                    profile_id=instance.pk,
                    company_id=default_company,
                    user_company_profile_id=user_company_profile_id,
                )
        else:
            instance = super().create(validated_data)
            ucp_service.update_profile_relation(
                profile_id=instance.pk,
                company_id=default_company,
                user_company_profile_id=user_company_profile_id,
            )
        UserService().update_fname_and_lname(user_id, validated_data)
        return instance
