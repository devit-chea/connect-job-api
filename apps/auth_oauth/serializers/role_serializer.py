from drf_writable_nested.serializers import WritableNestedModelSerializer
from rest_framework import serializers
from rest_framework.fields import CreateOnlyDefault

from apps.auth_oauth.constants.auth_constants import PermissionOptions
from apps.auth_oauth.constants.auth_constants import (
    UserTypes,
)
from apps.auth_oauth.models.permission_model import RolePermission, Permission
from apps.auth_oauth.models.role_model import Role
from apps.base.models.company_model import Company
from apps.base.serializers.base_serializer import BaseSerializer, BaseCompanySerializer
from apps.base.utils.base_util import get_default_company


class RoleInfoSerializer(BaseSerializer):
    class Meta:
        model = Role
        fields = ["id", "name", "code", "type", "company", "active", "description"]


class DefaultRolePermissionSerializer(BaseSerializer):
    perm_type = serializers.ChoiceField(required=True, choices=PermissionOptions)
    permission = serializers.PrimaryKeyRelatedField(queryset=Permission.objects.all())

    class Meta:
        model = RolePermission
        fields = ["id", "permission", "perm_type"]
        extra_kwargs = {
            "id": {"read_only": True},
        }


class DefaultRoleSerializer(WritableNestedModelSerializer, BaseSerializer):
    type = serializers.ChoiceField(choices=UserTypes.choices)
    role_permissions = DefaultRolePermissionSerializer(many=True, required=True)
    company = BaseCompanySerializer(read_only=True)  # READ
    company_id = serializers.PrimaryKeyRelatedField(  # WRITE
        source="company", queryset=Company.objects.all(),
        required=False, allow_null=True,
        default=CreateOnlyDefault(get_default_company),
        write_only=True,
    )
    name = serializers.CharField()
    is_public = serializers.BooleanField(default=True, required=False, allow_null=True)

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "code",
            "type",
            "company",
            "company_id",
            "active",
            "description",
            "own_only",
            "is_public",
            "role_permissions",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "name": {"required": True},
        }

    def to_internal_value(self, data):
        default_company = get_default_company()
        data["company"] = default_company.id if default_company else None

        return super().to_internal_value(data)
