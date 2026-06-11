from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.auth_oauth.models.profile_model import Profile
from django.db import models


class Portfolio(AbstractBaseModel):
    user_profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="portfolio_user_profile",
        null=True,
        blank=True,
    )
    project_name = models.CharField(max_length=255, null=True, blank=True)
    role = models.CharField(max_length=255, null=True, blank=True)
    brief_description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "portfolio"
        description = "Portfolio"
