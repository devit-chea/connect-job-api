from django.db import models

from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.job_management_app.models.job_application_model import JobApplicationModel
from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineConfigStepModel,
    JobPipelineStatusConfigModel,
)


class JobApplicationStatusHistoryModel(AbstractBaseModel):
    application = models.ForeignKey(JobApplicationModel, on_delete=models.CASCADE)
    step = models.ForeignKey(JobPipelineConfigStepModel, on_delete=models.CASCADE)
    status = models.ForeignKey(
        JobPipelineStatusConfigModel, on_delete=models.SET_NULL, null=True
    )

    from_step = models.ForeignKey(
        JobPipelineConfigStepModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    to_step = models.ForeignKey(
        JobPipelineConfigStepModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    to_status = models.ForeignKey(
        JobPipelineStatusConfigModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    is_auto = models.BooleanField(default=False)
    moved_to_next = models.BooleanField(default=False)
    note = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "job_application_status_history"
        ordering = ["-create_date"]
