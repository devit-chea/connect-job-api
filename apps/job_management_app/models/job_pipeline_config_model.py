from django.core.exceptions import ValidationError
from django.db import models

from apps.auth_totp_mail.models.mail_template_models import MailTemplate
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.abstract_model import AbstractBaseCompany
from apps.base.models.soft_delete_model import SoftDeleteModel


class Status(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    DELETED = "DELETED", "Deleted"


class JobPipelineStatusConfigModel(
    AbstractBaseModel, AbstractBaseCompany, SoftDeleteModel
):
    code = models.SlugField(max_length=64, null=True, blank=True)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    is_public = models.BooleanField(default=False)
    color = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table = "job_pipeline_status_config"
        indexes = [
            models.Index(fields=["company_id", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} (company={self.company_id})"


class JobPipelineConfigModel(AbstractBaseModel, AbstractBaseCompany, SoftDeleteModel):
    code = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=False, blank=False)
    description = models.CharField(max_length=255, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=False)

    status = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        db_table = "job_pipeline_config"
        description = "Job Pipeline Config Model"
        indexes = [
            models.Index(fields=["company_id", "is_active"]),
        ]

    def __str__(self):
        return self.name


class JobPipelineConfigStepModel(AbstractBaseModel, SoftDeleteModel):
    pipeline_config = models.ForeignKey(
        JobPipelineConfigModel,
        on_delete=models.CASCADE,
        related_name="steps",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255, null=False, blank=False)
    color = models.CharField(max_length=20, null=False, blank=False)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    is_default = models.BooleanField(default=False)
    is_offer = models.BooleanField(default=False)

    allowed_statuses = models.ManyToManyField(
        "JobPipelineStatusConfigModel",
        through="JobPipelineStepStatusConfigModel",
        related_name="steps",
        blank=True,
    )

    class Meta:
        db_table = "job_pipeline_config_step"
        description = "Job Pipeline Step Model"

    def __str__(self):
        return f"{self.name} (Pipeline: {self.pipeline_config_id})"


class JobPipelineStepStatusConfigModel(AbstractBaseModel, SoftDeleteModel):
    step = models.ForeignKey(
        JobPipelineConfigStepModel,
        on_delete=models.CASCADE,
        related_name="statuses",
    )

    status = models.ForeignKey(
        JobPipelineStatusConfigModel,
        on_delete=models.CASCADE,
        related_name="allowed_in_steps",
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "job_pipeline_step_status"
        unique_together = ("step", "status")
        indexes = [models.Index(fields=["step", "status"])]

    def clean(self):
        step_company_id = getattr(self.step.pipeline_config, "company_id", None)
        status_company_id = getattr(self.status, "company_id", None)
        status_company = getattr(self.status, "company", None)
        is_public_default = (
            getattr(self.status, "is_public", False)
            and getattr(status_company, "code", None) == "DEFAULT"
        )
        if status_company_id != step_company_id and not is_public_default:
            raise ValidationError(
                {
                    "status": "Status must belong to the same company as the step's pipeline."
                }
            )

    def __str__(self):
        return f"{self.status.name} (step={self.step_id})"


class JobPipelineStepPropertyDefaultConfigModel(AbstractBaseModel, SoftDeleteModel):
    step = models.OneToOneField(
        JobPipelineConfigStepModel,
        on_delete=models.CASCADE,
        related_name="defaults",
    )

    default_status = models.ForeignKey(
        JobPipelineStatusConfigModel, on_delete=models.PROTECT, related_name="+"
    )
    success_status = models.ForeignKey(
        JobPipelineStatusConfigModel,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    failed_status = models.ForeignKey(
        JobPipelineStatusConfigModel,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )

    success_mail_template_id = models.ForeignKey(
        MailTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    failed_mail_template_id = models.ForeignKey(
        MailTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    is_success_auto_send = models.BooleanField(default=False)
    is_failed_auto_send = models.BooleanField(default=False)

    class Meta:
        db_table = "job_pipeline_step_property_default"
        indexes = [models.Index(fields=["step"])]

    def clean(self):
        step_company_id = getattr(self.step.pipeline_config, "company_id", None)

        def _is_company_or_public_default(status: JobPipelineStatusConfigModel) -> bool:
            if status.company_id == step_company_id:
                return True
            company = getattr(status, "company", None)
            return (
                getattr(status, "is_public", False)
                and getattr(company, "code", None) == "DEFAULT"
            )

        for f in ("default_status", "success_status", "failed_status"):
            s = getattr(self, f)
            if not s:
                continue
            if not _is_company_or_public_default(s):
                raise ValidationError(
                    {
                        f: "Status must belong to this company or be a public DEFAULT catalog status."
                    }
                )
        allowed_ids = set(self.step.allowed_statuses.values_list("id", flat=True))
        for f in ("default_status", "success_status", "failed_status"):
            s = getattr(self, f)
            if s and s.id not in allowed_ids:
                raise ValidationError(
                    {f: "Status must be one of the step's allowed statuses."}
                )

        if self.is_success_auto_send and not self.success_mail_template_id:
            raise ValidationError(
                {"Mail Template is required when success auto-send is enabled."}
            )

        if self.is_failed_auto_send and not self.failed_mail_template_id:
            raise ValidationError(
                {"Mail Template is required when failed auto-send is enabled."}
            )

    def __str__(self):
        return f"Defaults(step={self.step_id})"
