from django.db import models
from django.contrib.contenttypes.models import ContentType

from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.abstract_model import AbstractBaseCompany


RESET_CHOICES = [
    ("manual", "Manual"),
    ("yearly", "Yearly"),
    ("monthly", "Monthly"),
    ("daily", "Daily"),
]


class Sequence(AbstractBaseModel, AbstractBaseCompany):
    name = models.CharField(max_length=255)
    reset_type = models.CharField(
        max_length=50, choices=RESET_CHOICES, default="manual"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    active = models.BooleanField(default=False)

    class Meta:
        db_table = "ir_sequence"
        description = "Sequence"


class SequenceDateRange(AbstractBaseModel):
    sequence = models.ForeignKey(
        Sequence, related_name="sequence_date_ranges", on_delete=models.CASCADE
    )
    active = models.BooleanField(default=False)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    prefix = models.CharField(max_length=255, blank=True, null=True)
    suffix = models.CharField(max_length=255, blank=True, null=True)
    padding = models.IntegerField(blank=True, null=True, default=0)
    increment_number = models.IntegerField(default=1)
    start_number = models.IntegerField(default=1)
    end_number = models.IntegerField(default=0)
    next_number = models.IntegerField(default=1)
    field_name = models.CharField(max_length=255, null=True)
    field_value = models.CharField(max_length=255, null=True)

    class Meta:
        db_table = "ir_sequence_date_range"
        description = "Sequence DateRange"
        ordering = ["create_date"]
