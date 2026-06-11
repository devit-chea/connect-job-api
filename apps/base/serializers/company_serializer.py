from django.db import transaction
from drf_extra_fields.relations import PresentablePrimaryKeyRelatedField
from drf_writable_nested import WritableNestedModelSerializer
from rest_framework import serializers

from apps.auth_oauth.constants.auth_constants import UserTypes
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.models.role_model import Role
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.auth_oauth.serializers.auth_serializer import UserInfoSerializer
from apps.auth_oauth.utils.auth_util import get_active_profile_id
from apps.base.constants.base_constants import CompanyStatusChoices, EntryTypeChoices
from apps.base.models.company_model import Company
from apps.base.models.country_model import Country
from apps.base.models.geo_area_model import GeoArea
from apps.base.serializers.base_serializer import BaseSerializer, BaseAndAuditSerializer
from apps.base.serializers.country_serializer import CountryInfoSerializer
from apps.base.serializers.geo_area_serializer import GeoAreaInfoSerializer
from apps.base.utils.file_management_util import FileURLService


class RequestCompanyLookUpSerializer(serializers.ModelSerializer):
    city = PresentablePrimaryKeyRelatedField(
        queryset=GeoArea.objects.all(),
        presentation_serializer=GeoAreaInfoSerializer,
        required=False,
        allow_null=True,
    )
    country = PresentablePrimaryKeyRelatedField(
        queryset=Country.objects.all(),
        presentation_serializer=CountryInfoSerializer,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "industry",
            "found_date",
            "address",
            "country",
            "city",
            "postal_code",
            "phone_number",
            "email",
            "linkedin_email",
            "website",
            "profile_picture_id",
            "status",
            "is_active",
            "is_existed",
        ]
        
    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get("file_path")
        data["cover_image_url"] = (presentation.get("cover_image") or {}).get("file_path")
        return data


class CompanyLookUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["id", "name", "email", "profile_picture_id", "status", "is_active"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        include_cover = self.context.get("include_cover", True)
        presentation = FileURLService.present_profile_images(instance, include_cover=include_cover)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get("file_path")
        data["cover_image_url"] = (presentation.get("cover_image") or {}).get("file_path")
        return data


class ParentCompanyInfoSerializer(BaseSerializer):
    class Meta:
        model = Company
        fields = ["id", "name", "website"]


class CompanySerializer(WritableNestedModelSerializer, BaseAndAuditSerializer):
    inject_company_id = False
    parent = PresentablePrimaryKeyRelatedField(
        queryset=Company.objects.all(),
        presentation_serializer=ParentCompanyInfoSerializer,
        required=False,
        allow_null=True,
    )
    assign_admin = PresentablePrimaryKeyRelatedField(
        queryset=User.objects.all(),
        presentation_serializer=UserInfoSerializer,
        required=False,
        allow_null=True,
    )
    name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    city = PresentablePrimaryKeyRelatedField(
        queryset=GeoArea.objects.all(),
        presentation_serializer=GeoAreaInfoSerializer,
        required=False,
        allow_null=True,
    )
    country = PresentablePrimaryKeyRelatedField(
        queryset=Country.objects.all(),
        presentation_serializer=CountryInfoSerializer,
        required=False,
        allow_null=True,
    )
    found_date = serializers.CharField(allow_blank=True, required=False)

    class Meta:
        model = Company
        fields = "__all__"

    def validate_name(self, value: str):
        """Normalize name to lowercase and ensure uniqueness."""
        if not value:
            return value

        normalized_name = value.strip().lower()

        qs = Company.objects.filter(name__iexact=normalized_name)

        # Exclude current instance if updating
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError(
                f"Company with name '{normalized_name}' already exists."
            )

        return normalized_name

    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get("file_path")
        data["cover_image_url"] = (presentation.get("cover_image") or {}).get("file_path")
        return data


class CompaniesListSerializer(WritableNestedModelSerializer, BaseSerializer):
    job_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "email",
            "phone_number",
            "address",
            "website",
            "industry",
            "company_size",
            "about_me",
            "is_active",
            "job_count",
            "industry",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get("file_path")
        data["cover_image_url"] = (presentation.get("cover_image") or {}).get("file_path")
        return data


class RecruiterCompaniesListSerializer(WritableNestedModelSerializer, BaseSerializer):
    job_count = serializers.IntegerField(read_only=True)
    user_type = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "email",
            "phone_number",
            "address",
            "website",
            "industry",
            "company_size",
            "about_me",
            "is_active",
            "job_count",
            "user_type",
            "industry",
        ]

    def get_user_type(self, instance):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not request or not user or user.is_anonymous:
            return None
        ucp = (
            UserCompanyProfile.objects
            .filter(user=user, company=instance)
            .only("type")
            .first()
        )
        return ucp.type if ucp else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get("file_path")
        data["cover_image_url"] = (presentation.get("cover_image") or {}).get("file_path")
        return data


class CompanyRequestWithAdminRecruiterSerializer(WritableNestedModelSerializer, BaseAndAuditSerializer):
    parent_id = serializers.PrimaryKeyRelatedField(
        source="parent",
        queryset=Company.objects.all(),
        required=False,
        allow_null=True,
    )
    city_id = serializers.PrimaryKeyRelatedField(
        source="city",
        queryset=GeoArea.objects.all(),
        required=True,
        allow_null=False,
    )
    country_id = serializers.PrimaryKeyRelatedField(
        source="country",
        queryset=Country.objects.all(),
        required=True,
        allow_null=False,
    )
    existed_company_id = serializers.PrimaryKeyRelatedField(
        source="existed_company",
        queryset=Company.objects.all(),
        required=False,
        allow_null=True,
    )

    profile_picture_id = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    cover_picture_id = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    industry = serializers.CharField()
    found_date = serializers.CharField()
    address = serializers.CharField()
    phone_number = serializers.CharField()
    email = serializers.EmailField()
    about_me = serializers.CharField()

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "email",
            "website",
            "street",
            "phone_number",
            "address",
            "city_id",
            "city_name",
            "country_id",
            "postal_code",
            "industry",
            "linkedin_email",
            "description",
            "about_me",
            "company_size",
            "email_mask",
            "phone_mask",
            "logo_description",
            "found_date",
            "parent_id",
            "existed_company_id",
            "access_type",
            "is_agree_policy",
            "profile_picture_id",
            "cover_picture_id",
            "status",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
        }

    def validate(self, attrs):
        name = attrs.get("name")
        if Company.objects.filter(name__iexact=name).exists():
            raise serializers.ValidationError("A company with this name already exists.")
        return attrs

    @transaction.atomic()
    def create(self, validated_data):
        request = self.context.get("request")
        if not request or not request.user or request.user.is_anonymous:
            raise serializers.ValidationError("Authenticated user is required.")
        user = request.user
        active_profile_id, _ = get_active_profile_id(request)
        profile_info = Profile.objects.filter(id=active_profile_id).first()

        # temporary use this as company-field
        # profile_picture_id = validated_data.pop("profile_picture_id", None)
        # cover_picture_id = validated_data.pop("cover_picture_id", None)
        admin_roles = list(Role.objects.filter(type=UserTypes.ADMIN_RECRUITER.value, code="ADMIN_RECRUITER_ROLE"))
        if not admin_roles:
            raise serializers.ValidationError("No ADMIN_RECRUITER role configured.")

        requested_status = validated_data.pop("status", None)
        final_status = CompanyStatusChoices.PENDING.value
        if requested_status == CompanyStatusChoices.DRAFT.value:
            final_status = CompanyStatusChoices.DRAFT.value
         # company
        company = Company.objects.create(
            **validated_data,
            status=final_status,
            entry_type=EntryTypeChoices.ADDITIONAL.value,
            is_active=False,
            is_existed=False,
        )
        # ucp
        user_company_payload = {
            "user": user.pk,
            "company": company.pk,
            "type": UserTypes.ADMIN_RECRUITER.value,
            "roles": [r.id for r in admin_roles],
        }
        from apps.auth_oauth.serializers.admin_user_serializer import RecruiterRequestCompanyAssignRolesSerializer
        ucp_serializer = RecruiterRequestCompanyAssignRolesSerializer(
            data=user_company_payload,
            context={**self.context, "profile_info": profile_info}
        )
        ucp_serializer.is_valid(raise_exception=True)
        user_company_profile = ucp_serializer.save()

        if not getattr(user, "default_user_profile_company", None):
            user.default_user_profile_company = user_company_profile.pk
            user.save(update_fields=["default_user_profile_company"])
        return company

