import json

from django.db import models

from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.soft_delete_model import SoftDeleteModel
from apps.job_management_app.models.job_post_model import JobPostModel


class QuestionTypes(models.TextChoices):
    TEXT = "TEXT", "Text"
    SINGLE_CHOICE = "SINGLE_CHOICE", "Single Choice"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE", "Multiple Choice"


class JobPostQuestionModel(AbstractBaseModel, SoftDeleteModel):
    job_post = models.ForeignKey(
        JobPostModel, on_delete=models.CASCADE, related_name="questions"
    )
    question_title = models.TextField()
    question_type = models.CharField(
        max_length=50, choices=QuestionTypes.choices, default=QuestionTypes.TEXT
    )
    is_required = models.BooleanField(default=False)
    choices = models.TextField(null=True, blank=True)  # Required only for type "choice"
    order = models.PositiveIntegerField(default=0)

    @property
    def choices_list(self):
        if self.choices:
            try:
                return json.loads(self.choices)
            except json.JSONDecodeError:
                return []
        return []

    @choices_list.setter
    def choices_list(self, value):
        if isinstance(value, list):
            self.choices = json.dumps(value)
        else:
            self.choices = None

    class Meta:
        db_table = "job_post_question"
        ordering = ["order"]
