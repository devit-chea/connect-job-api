from django.db import models
from apps.auth_oauth.models.profile_model import Profile
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.company_model import Company


class Reference(AbstractBaseModel):
    user_profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="reference_user_profile",
        null=True,
        blank=True,
    )
    reference_name = models.CharField(max_length=255, null=True, blank=True)
    job_title = models.CharField(max_length=255, null=True, blank=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        related_name="reference_company",
        null=True,
        blank=True,
    )
    email = models.EmailField(max_length=254, null=True, blank=True)
    phone_number = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "reference"
        description = "Reference"
