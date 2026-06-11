from django.db import models
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.company_model import Company
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.models.role_model import Role


class UserCompanyProfile(AbstractBaseModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        related_name="user_company_profile_company",
        null=True,
        blank=True,
    )
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="user_company_profile_user",
        null=True,
        blank=True,
    )
    type = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=255, null=True, blank=True)
    code = models.CharField(max_length=255, null=True, blank=True)
    provider = models.CharField(max_length=255, null=True, blank=True)
    state = models.CharField(max_length=255, null=True, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    roles = models.ManyToManyField(Role, blank=True, related_name="roles_related")

    class Meta:
        db_table = "user_company_profile"
