from django.db import models

from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.abstract_model import AbstractBaseCompany
from apps.base.models.soft_delete_model import SoftDeleteModel


class StatusTypes(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    DELETED = "DELETED", "Deleted"


class QuestionTypes(models.TextChoices):
    TEXT = "TEXT", "Text"
    SINGLE_CHOICE = "SINGLE_CHOICE", "Single Choice"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE", "Multiple Choice"


class JobQuestionTemplateConfigModel(
    AbstractBaseModel, AbstractBaseCompany, SoftDeleteModel
):
    template_name = models.CharField(max_length=255, blank=False, null=False)
    description = models.CharField(max_length=500, blank=True, null=True)
    is_active = models.BooleanField(default=False)
    status = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=StatusTypes.choices,
        default=StatusTypes.INACTIVE,
    )
    is_public = models.BooleanField(default=False)

    class Meta:
        db_table = "job_question_template_config"
        description = "Job Question Template Config Model"


class JobQuestionConfigModel(SoftDeleteModel):
    question_template = models.ForeignKey(
        JobQuestionTemplateConfigModel,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    question_title = models.TextField(blank=False, null=False)
    question_type = models.CharField(
        max_length=50, choices=QuestionTypes.choices, default=QuestionTypes.TEXT
    )
    choices = models.JSONField(default=list, blank=True, null=True)
    is_required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "job_question_config"
        description = "Job Question Config Model"
