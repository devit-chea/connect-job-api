from django.db import models
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.auth_oauth.constants.auth_constants import GroupTypes, PermissionTypes
from apps.auth_oauth.constants.auth_constants import PermissionOptions
from apps.auth_oauth.models.role_model import Role


class Permission(AbstractBaseModel):
    name = models.CharField(blank=True, null=True)
    codename = models.CharField(blank=True, null=True, unique=True)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        default=PermissionTypes.PERMISSION,
        choices=PermissionTypes,
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    group = models.CharField(
        max_length=50,
        blank=True,
        default=GroupTypes.RECRUITER,
        choices=GroupTypes,
    )
    custom_type = models.JSONField(default=list, blank=True, null=True)

    class Meta:
        db_table = "permissions"


class RolePermission(AbstractBaseModel):
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="role_permissions",
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="role_permissions_related",
    )
    perm_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        default=PermissionOptions.DENIED,
        choices=PermissionOptions,
    )

    class Meta:
        db_table = "role_permissions"
