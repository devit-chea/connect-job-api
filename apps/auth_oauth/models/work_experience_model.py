from django.db import models

from apps.auth_oauth.models.profile_model import Profile
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.company_model import Company
from apps.base.models.geo_area_model import GeoArea


class WorkExperience(AbstractBaseModel):
    user_profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="work_experience_user_profile",
        null=True,
        blank=True,
    )
    job_title = models.CharField(max_length=255, null=True, blank=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        related_name="work_experience_company",
        null=True,
        blank=True,
    )
    location = models.ForeignKey(
        GeoArea,
        on_delete=models.CASCADE,
        related_name="work_experience_location",
        null=True,
        blank=True,
    )
    location_name = models.CharField(max_length=255, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    job_description = models.TextField(null=True, blank=True)
    is_currently_work = models.BooleanField(default=False)

    class Meta:
        db_table = "work_experience"
        description = "Work Experience"
        ordering = ["-create_date"]
