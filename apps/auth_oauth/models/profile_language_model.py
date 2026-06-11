from django.db import models

from apps.auth_oauth.constants.auth_constants import LanguageLevels
from apps.auth_oauth.models.profile_model import Profile
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.language_model import Language


class ProfileLanguage(AbstractBaseModel):
    user_profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="profile_language_user",
        null=True,
        blank=True,
    )
    language = models.ForeignKey(
        Language,
        on_delete=models.SET_NULL,
        related_name="profile_language",
        null=True,
        blank=True,
    )
    level = models.CharField(
        choices=LanguageLevels, default=LanguageLevels.BEGINNER, null=True, blank=True
    )
    language_name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "profile_language"
