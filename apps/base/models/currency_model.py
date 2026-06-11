from django.db import models
from apps.base.models.abstract_base_model import AbstractBaseModel
from django.core.validators import MinLengthValidator

class Currency(AbstractBaseModel):
    code = models.CharField(
        unique=True,
        max_length=5,
        blank=False,
        null=False,
        validators=[MinLengthValidator(3)],
    )
    name = models.CharField(max_length=100, blank=False, null=False)
    name_plural = models.CharField(max_length=100, blank=False, null=False)
    symbol = models.CharField(max_length=50, blank=False, null=False)
    symbol_native = models.CharField(max_length=50, blank=False, null=False)

    class Meta:
        db_table = "currencies"
        description = "Root Currencies"