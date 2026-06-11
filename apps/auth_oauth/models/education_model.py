from django.db import models

from apps.auth_oauth.models.profile_model import Profile
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.geo_area_model import GeoArea
from apps.base.models.institution_model import Institution


class Education(AbstractBaseModel):
    user_profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="education_user_profile",
        null=True,
        blank=True,
    )
    institution_name = models.CharField(max_length=255, null=True, blank=True)
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        related_name="education_institution",
        null=True,
        blank=True,
    )
    degree = models.CharField(max_length=255, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    location = models.ForeignKey(
        GeoArea,
        on_delete=models.CASCADE,
        related_name="education_location",
        null=True,
        blank=True,
    )
    location_name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    study_field = models.CharField(max_length=255, null=True, blank=True)
    is_currently_study = models.BooleanField(default=False)

    class Meta:
        db_table = "education"
        ordering = ["-create_date"]
