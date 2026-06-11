from drf_extra_fields.relations import PresentablePrimaryKeyRelatedField
from rest_framework import serializers

from apps.auth_oauth.serializers.user_company_profile_serializer import (
    CompanyEmployeeSerializer,
)
from apps.base.constants.base_constants import Status
from apps.base.models.company_model import Company
from apps.base.models.country_model import Country
from apps.base.models.geo_area_model import GeoArea
from apps.base.serializers.base_serializer import BaseSerializer
from apps.base.serializers.country_serializer import CountryInfoSerializer
from apps.base.serializers.geo_area_serializer import GeoAreaInfoSerializer
from apps.base.utils.file_management_util import (
    FileURLService,
    ImageListSerializer,
    resolve_profile_images,
)


class AdminCompanySerializer(BaseSerializer):
    email = serializers.EmailField()
    phone_number = serializers.CharField()
    address = serializers.CharField()
    industry = serializers.CharField()
    name = serializers.CharField()
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
    is_agree_policy = serializers.BooleanField(required=False, default=True)

    class Meta:
        model = Company
        list_serializer_class = ImageListSerializer
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
            "profile_picture_id",
            "cover_picture_id",
            "city",
            "country",
            "access_type",
            "is_agree_policy",
        ]
        read_only_fields = ["id", "create_date", "write_date"]

    def validate_name(self, value):
        instance = getattr(self, "instance", None)
        if (
            value
            and Company.objects.filter(name__exact=value)
            .exclude(id=instance.id if instance else None)
            .exists()
        ):
            raise serializers.ValidationError("Company Name already exists!")
        return value

    def create(self, validated_data):
        validated_data["status"] = Status.APPROVED
        return super().create(validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update(resolve_profile_images(instance, self.context))
        return data


class AdminCompanyDetailSerializer(BaseSerializer):
    email = serializers.EmailField()
    phone_number = serializers.CharField()
    address = serializers.CharField()
    industry = serializers.CharField()
    name = serializers.CharField()
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
    is_agree_policy = serializers.BooleanField(required=False, default=True)
    employees = serializers.SerializerMethodField()

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
            "profile_picture_id",
            "cover_picture_id",
            "city",
            "country",
            "access_type",
            "is_agree_policy",
            "employees",
        ]
        read_only_fields = ["id", "create_date", "write_date"]

    def validate_name(self, value):
        instance = getattr(self, "instance", None)
        if (
            value
            and Company.objects.filter(name__exact=value)
            .exclude(id=instance.id if instance else None)
            .exists()
        ):
            raise serializers.ValidationError("Company Name already exists!")
        return value

    def get_employees(self, instance):
        qs = instance.user_company_profile_company.select_related("profile").only(
            "id",
            "type",
            "status",
            "profile__full_name",
            "profile__email",
            "profile__profile_picture_id",
        )
        return CompanyEmployeeSerializer(qs, many=True).data

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
