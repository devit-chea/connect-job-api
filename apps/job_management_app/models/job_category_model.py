from django.db import models

from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.soft_delete_model import SoftDeleteModel
from apps.base.models.abstract_model import AbstractBaseCompany


class JobCategoryModel(AbstractBaseModel, SoftDeleteModel, AbstractBaseCompany):
    name = models.CharField(max_length=255, null=False, blank=False)
    code = models.CharField(max_length=50, blank=True, default="")
    description = models.CharField(max_length=500, blank=True, default="")
    profile_picture_id = models.CharField(max_length=36, blank=True, null=True)

    class Meta:
        db_table = "job_categories"
        description = "Job Post Additional Field Model"
