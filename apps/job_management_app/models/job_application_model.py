from django.db import models
from django.utils import timezone

from apps.auth_oauth.models.profile_model import Profile
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.soft_delete_model import SoftDeleteModel
from apps.job_management_app.constants.job_application_types import (
    EmploymentStatus,
    JobApplicationStatus,
)
from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineConfigModel,
    JobPipelineConfigStepModel,
    JobPipelineStatusConfigModel,
)
from apps.job_management_app.models.job_post_model import JobPostModel
from apps.job_management_app.models.job_question_model import JobPostQuestionModel


class JobApplicationModel(AbstractBaseModel, SoftDeleteModel):
    job_post = models.ForeignKey(JobPostModel, on_delete=models.CASCADE)
    applicant_name = models.CharField(max_length=250, blank=True, null=True)
    applicant_current_position = models.CharField(max_length=250, blank=True, null=True)
    apply_date = models.DateTimeField(default=timezone.now)
    apply_message = models.TextField(blank=True, null=True)
    cv_file_id = models.CharField(max_length=36, blank=True, null=True)
    cover_letter_file_id = models.CharField(max_length=36, blank=True, null=True)
    additional_file_ids = models.JSONField(null=True, blank=True)
    meta_data = models.JSONField(null=True, blank=True)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    status = models.CharField(
        max_length=50,
        choices=JobApplicationStatus.choices,
        default=JobApplicationStatus.ACTIVE,
        null=True,
        blank=True,
    )

    pipeline_config = models.ForeignKey(
        JobPipelineConfigModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="job_applications",
        help_text="Linked pipeline config. If set, pipeline_text should be null.",
    )
    pipeline_text = models.TextField(
        null=True,
        blank=True,
        help_text="Fallback pipeline config text for external integration. Used only if pipeline_config_id is null.",
    )
    pipeline_step = models.ForeignKey(
        JobPipelineConfigStepModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="job_applications",
        help_text="Current step within the pipeline.",
    )
    pipeline_status = models.ForeignKey(
        JobPipelineStatusConfigModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="job_applications",
        help_text="Current status inside the step.",
    )

    # Snapshots
    pipeline_step_order = models.PositiveIntegerField(default=0)
    pipeline_status_order = models.PositiveIntegerField(default=0)
    pipeline_step_name = models.CharField(max_length=120, blank=True, default="")
    pipeline_status_name = models.CharField(max_length=120, blank=True, default="")

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, null=True)
    score = models.FloatField(
        db_comment="Store score for applied applicant.", null=True
    )
    employment_status = models.CharField(
        max_length=50,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.ACTIVE.value,
        blank=True,
    )
    expected_salary = models.DecimalField(
        null=True,
        blank=True,
        max_digits=12,
        decimal_places=2,
    )
    code = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "job_application"
        description = "Job Application Model"
        indexes = [
            models.Index(fields=["job_post"]),
            models.Index(fields=["pipeline_step"]),
            models.Index(fields=["pipeline_status"]),
            models.Index(fields=["pipeline_step_order", "pipeline_status_order"]),
            models.Index(fields=["create_ucp_id", "job_post", "is_deleted"]),
        ]

    def __str__(self):
        return f"Applied to {self.job_post}"


class JobApplicationQuestionAnswerModel(AbstractBaseModel, SoftDeleteModel):
    application = models.ForeignKey(
        JobApplicationModel, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(
        JobPostQuestionModel,
        on_delete=models.CASCADE,
        related_name="application_answers",
    )

    answer = models.TextField()

    class Meta:
        db_table = "job_application_question_answer"
        ordering = ["id"]
        unique_together = ("application", "question")

    def __str__(self):
        return f"Answer to {self.question} by {self.application.user}"
