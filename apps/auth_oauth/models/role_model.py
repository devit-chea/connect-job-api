from django.db import models

from apps.auth_oauth.constants.auth_constants import UserTypes
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.company_model import Company


class Role(AbstractBaseModel):
    name = models.CharField(blank=True, null=True)
    code = models.CharField(blank=True, null=True)
    type = models.CharField(
        choices=UserTypes, blank=True, null=True
    )  # type of user profile
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="role_company",
        null=True,
        blank=True,
    )
    own_only = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    is_public = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False,db_comment="ucp default assignment roles ")
    class Meta:
        db_table = "roles"
