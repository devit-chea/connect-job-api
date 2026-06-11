from apps.base.models.abstract_base_model import AbstractBaseModel
from django.db import models


class ApplicantConfig(AbstractBaseModel):
    field_types = [
        ("position_title", "Position Title"),
        ("employment_type", "Employment Type"),
        ("job_location", "Job Location"),
        ("remote_type", "Remote Type"),
        ("job_category", "Job Category"),
    ]

    value = models.CharField(max_length=255, null=True, blank=True)
    field_name = models.CharField(
        max_length=255, null=True, blank=True, choices=field_types
    )

    class Meta:
        unique_together = ("field_name", "value")
        db_table = "applicant_config"
        description = "Applicant Configuration"
