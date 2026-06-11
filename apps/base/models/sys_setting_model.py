from django.db import models

from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.abstract_model import AbstractBaseCompany


class SysSetting(AbstractBaseModel, AbstractBaseCompany):
    name = models.CharField(max_length=100)
    value = models.TextField()
    description = models.CharField(max_length=250, blank=True, null=True)
    first_value = models.BooleanField(default=False)

    class Meta:
        db_table = "sys_setting"
        description = "System Setting"
