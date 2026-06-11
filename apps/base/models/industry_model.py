from django.db import models

from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.abstract_model import AbstractBaseCompany, AbstractReferenceNo


class IndustryModel(AbstractBaseModel, AbstractBaseCompany, AbstractReferenceNo):
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, null=True)

    class Meta:
        db_table = "industry"
        description = "Company Industry"
