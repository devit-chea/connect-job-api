from decimal import Decimal

from django.db.backends.postgresql.psycopg_any import NumericRange
from rest_framework import serializers

from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.base.mixins.base_serializer_mixins import BaseReadOnlyFieldsMixin
from apps.base.models.company_model import Company
from apps.base.utils.file_management_util import (
    FileURLService,
    ImageListSerializer,
    resolve_profile_images,
)


class BaseSerializer(serializers.ModelSerializer):

    def create(self, validated_data):
        validated_data = self.add_uid(validated_data, "create_uid")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self.add_uid(validated_data, "write_uid")
        return super().update(instance, validated_data)

    def add_uid(self, validated_data, field_name):
        request = self.context.get("request", None)
        validated_data[field_name] = request.user.id if request else None
        return validated_data


class BaseAndAuditSerializer(BaseSerializer):
    """
    Extends BaseSerializer by injecting audit fields (create_ucp_id, write_ucp_id)
    and company_id during create/update. This version separates company_id logic.
    """

    # Default: inject company_id unless override set to False
    inject_company_id = True

    def create(self, validated_data):
        validated_data = self.add_audit_fields(validated_data, ucp_id_field="create_ucp_id")
        if self.inject_company_id:
            validated_data = self.add_company_id(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self.add_audit_fields(validated_data, ucp_id_field="write_ucp_id")
        if self.inject_company_id:
            validated_data = self.add_company_id(validated_data)
        return super().update(instance, validated_data)

    def add_audit_fields(self, validated_data, ucp_id_field):
        request = self.context.get("request", None)
        if request:
            validated_data[ucp_id_field] = getattr(request, "user_company_profile_id", None)
        else:
            validated_data[ucp_id_field] = None
        return validated_data

    def add_company_id(self, validated_data):
        request = self.context.get("request", None)
        if not request:
            raise serializers.ValidationError("No request context available.")
        company_id = getattr(request, "company_id", None)
        if company_id is None:
            ucp_id = getattr(request, "user_company_profile_id", None)
            if ucp_id is None:
                raise serializers.ValidationError("No active user company profile.")
            ucp = (
                UserCompanyProfile.objects
                .select_related("company")
                .filter(id=ucp_id, company__is_active=True)
                .first()
            )
            if not ucp or not ucp.company_id:
                raise serializers.ValidationError("No active company.")
            company_id = ucp.company_id
        validated_data["company_id"] = company_id
        return validated_data


class BaseCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        list_serializer_class = ImageListSerializer
        fields = [
            "id",
            "name",
            "email",
            "website",
            "profile_picture_id",
            "cover_picture_id",
            "status",
            "is_active",
            "phone_number",
            "company_size",
            "found_date",
            "address",
            "about_me",
            "industry",
            "linkedin_email",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update(resolve_profile_images(instance,self.context))
        return data


class BaseDecimalRangeSerializerField(serializers.Field):
    def to_internal_value(self, data):

        if data in (None, []):
            return None

        if not isinstance(data, (list, tuple)) or len(data) != 2:
            raise serializers.ValidationError("Salary range must be a list of two numbers.")
        start, end = data
        try:
            start = Decimal(start) if start is not None else None
            end = Decimal(end) if end is not None else None
        except Exception:
            raise serializers.ValidationError("Range bounds must be valid decimal numbers.")

        # Create NumericRange inclusive on both ends (adjust bounds as needed)
        return NumericRange(start, end, '[]')

    def to_representation(self, value):
        if value is None:
            return None
        return [
            Decimal(value.lower) if value.lower is not None else None,
            Decimal(value.upper) if value.upper is not None else None,
        ]


class BaseReadOnlyFieldsSerializer(BaseReadOnlyFieldsMixin, serializers.ModelSerializer):
    """
    Base serializer that dynamically includes common audit fields as read-only.
    """
    pass  # no extra code needed, mixin and ModelSerializer handle everything


class BaseValidationSerializer(serializers.ModelSerializer):
    """
    Generic base serializer for:
    - Consistent required/blank messages
    - Default values
    - Cross-field validation
    """
    default_values = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Consistent required/blank messages
        for field_name, field in self.fields.items():
            if getattr(field, "required", False):
                field.error_messages["required"] = "This field may not be blank."
            if getattr(field, "allow_blank", False):
                field.error_messages["blank"] = "This field may not be blank."

    def validate(self, attrs):
        # Apply default values
        for field_name, default_value in getattr(self, "default_values", {}).items():
            if field_name not in attrs or attrs[field_name] is None:
                attrs[field_name] = default_value(attrs) if callable(default_value) else default_value

        # Cross-field validation hook
        return self.cross_field_validation(attrs)

    def cross_field_validation(self, attrs):
        """
        Override in child serializer for cross-field validation.
        """
        return attrs


class CompanyDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            "id", 
            "name", 
            "phone_number", 
            "industry",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get("file_path")
        return data
