from django.db import models
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.auth_oauth.models.profile_model import Profile


class Link(AbstractBaseModel):
    user_profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="link_user_profile",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255, null=True, blank=True)
    url = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "link"
