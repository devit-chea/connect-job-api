from django.db import models


class MailSpecificTypes(models.TextChoices):
    # Recruitment Pipeline
    PIPELINE_SUCCESS = "pipeline.success", "Success Pipeline"
    PIPELINE_FAILED = "pipeline.failed", "Failed Pipeline"

    # Applicant Apply Job
    APPLICANT_APPLY_JOB = "application.submit", "Applicant Apply Job"
