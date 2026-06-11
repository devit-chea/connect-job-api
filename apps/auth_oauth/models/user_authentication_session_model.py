from django.db import models
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.auth_oauth.models.auth_models import User


class UserAuthenticationSession(AbstractBaseModel):

    os = models.CharField(max_length=255, null=True, blank=True)
    os_version = models.CharField(max_length=255, null=True, blank=True)
    device = models.CharField(max_length=255, null=True, blank=True)
    device_branch = models.CharField(max_length=255, null=True, blank=True)
    device_model = models.CharField(max_length=255, null=True, blank=True)
    browser = models.CharField(max_length=255, null=True, blank=True)
    browser_version = models.CharField(max_length=255, null=True, blank=True)
    ip_address = models.CharField(max_length=100, null=True, blank=True)
    user_company_profile = models.ForeignKey(
        UserCompanyProfile,
        on_delete=models.SET_NULL,
        related_name="session_user_company_profile",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="session_user",
        null=True,
        blank=True,
    )
    type = models.CharField(max_length=255, null=True, blank=True)
    remark = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "user_authentication_session"
        description = "User Authentication Session"
