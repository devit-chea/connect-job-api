from django.db import transaction
from django.utils import timezone
from drf_writable_nested import WritableNestedModelSerializer
from rest_framework import serializers
from wdg_storage.base import WdgStorageMixin

from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.base.constants.base_constants import CompanyStatusChoices, EntryTypeChoices
from apps.base.models.company_model import Company
from apps.base.models.country_model import Country
from apps.base.models.geo_area_model import GeoArea
from apps.base.serializers.base_serializer import BaseSerializer, BaseAndAuditSerializer
from apps.base.utils.file_management_util import FileURLService


class CompanyResubmitSerializer(WritableNestedModelSerializer, BaseAndAuditSerializer):
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
            "access_type",
            "is_agree_policy",
            "profile_picture_id",
            "cover_picture_id",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
        }

    @transaction.atomic()
    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        MAX_REJECT = 3
        rejected_count = Profile.objects.filter(user=user, status="rejected").count()
        if rejected_count >= MAX_REJECT:
            raise serializers.ValidationError(
                {
                    "detail": f"Resubmission limit reached: {rejected_count} rejected submissions already."
                }
            )
        ucp_id = request.auth.payload.get("user_company_profile_id", None)
        if ucp_id is None:
            raise serializers.ValidationError(
                {"detail": "No active user company profile."}
            )
        ucp = (
            UserCompanyProfile.objects.select_related("company", "profile")
            .filter(id=ucp_id)
            .first()
        )
        if not ucp or not ucp.company:
            raise serializers.ValidationError(
                {"detail": "No active company found for resubmission."}
            )

        rejected_company = ucp.company
        if rejected_company.status != "rejected":
            raise serializers.ValidationError(
                {"detail": "Company is not rejected, cannot resubmit."}
            )
        new_company = Company.objects.create(
            **validated_data,
            status=CompanyStatusChoices.PENDING.value,
            is_active=False,
            is_existed=False,
            entry_type=EntryTypeChoices.ADDITIONAL.value,
        )
        existing_profile = ucp.profile
        defaults = {
            "first_name": existing_profile.first_name,
            "last_name": existing_profile.last_name,
            "full_name": existing_profile.full_name
            or f"{existing_profile.first_name} {existing_profile.last_name}".strip(),
            "gender": existing_profile.gender,
            "date_of_birth": existing_profile.date_of_birth,
            "phone_number": existing_profile.phone_number,
            "email": existing_profile.email,
            "location": existing_profile.location,
            "linkedin_profile": existing_profile.linkedin_profile,
            "website": existing_profile.website,
            "current_position": existing_profile.current_position,
            "about_me": existing_profile.about_me,
            "location_name": existing_profile.location_name,
            "department": existing_profile.department,
            "profile_type": "admin_recruiter",
            "status": "pending",
            "profile_picture_id": existing_profile.profile_picture_id,
            "cover_picture_id": existing_profile.cover_picture_id,
            "submitted_date": timezone.now(),
            "request_type": "new_company",
        }
        new_profile = Profile.objects.create(
            user=ucp.user, company=new_company, **defaults
        )
        ucp.company = new_company
        ucp.profile = new_profile
        ucp.save(update_fields=["company", "profile"])

        if getattr(user, "default_user_profile_company", None) != ucp.id:
            user.default_user_profile_company = ucp.id
            user.save(update_fields=["default_user_profile_company"])

        return new_company


class CompanyProfileImagesUpdateSerializer(BaseSerializer, WdgStorageMixin):
    """
    Update ONLY profile/cover image references.
    """

    profile_picture_id = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    cover_picture_id = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    class Meta:
        model = Company
        fields = [
            "id",
            "profile_picture_id",
            "cover_picture_id",
        ]
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
            for file_id in files
            if file_id and str(file_id).strip()
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
            for file_id in files
            if file_id and str(file_id).strip()
        ]
        self.update_metadata(files_data)
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get(
            "file_path"
        )
        data["cover_image_url"] = (presentation.get("cover_image") or {}).get(
            "file_path"
        )
        return data
