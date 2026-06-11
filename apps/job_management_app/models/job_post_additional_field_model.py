from django.db import models

from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.soft_delete_model import SoftDeleteModel
from apps.job_management_app.models.job_post_model import JobPostModel


class JobPostAdditionalFieldModel(AbstractBaseModel, SoftDeleteModel):
    job_post = models.ForeignKey(
        JobPostModel,
        on_delete=models.CASCADE,
        related_name="additional_field",
        db_column="job_post_id",
    )
    code = models.CharField(max_length=50, null=True, blank=True)
    name = models.CharField(max_length=250, null=True, blank=True)
    description = models.CharField(max_length=500, null=True, blank=True)
    field_name = models.CharField(max_length=250, null=True, blank=True)

    class Meta:
        db_table = "job_post_additional_field"
        description = "Job Post Additional Field Model"
