from django.db import models
from apps.base.models.abstract_base_model import AbstractBaseModel


class Institution(AbstractBaseModel):
    name = models.CharField(max_length=200)
    logo_url = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "institution"
        description = "Institution"
