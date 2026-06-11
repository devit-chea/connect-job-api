from django.db import models

from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.soft_delete_model import SoftDeleteModel
from apps.job_management_app.models.job_post_model import JobPostModel


class JobPostPipelineStepHistoryModel(AbstractBaseModel):
    job_post = models.ForeignKey(
        JobPostModel,
        on_delete=models.CASCADE,
        related_name="pipeline_step_history",
        null=True,
        blank=True,
    )
    step_code = models.CharField(max_length=50, null=True, blank=True)
    step_name = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = "job_post_pipeline_step_history"
