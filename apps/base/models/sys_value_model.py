from django.db import models
from django.contrib.postgres.fields import IntegerRangeField
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.abstract_model import AbstractBaseCompany



class SysValueCategories(AbstractBaseModel):
    name = models.CharField(max_length=200)

    class Meta:
        db_table = "sys_value_categories"
        description = "System Categories"


class SysValue(AbstractBaseModel, AbstractBaseCompany):
    code = models.CharField(max_length=200, blank=True, null=True)
    name = models.CharField(max_length=200)
    description = models.CharField(max_length=250, blank=True, null=True)
    order_index = models.IntegerField(default=0)
    default = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    properties = models.TextField(blank=True, null=True)
    category = models.ForeignKey(
        SysValueCategories,
        related_name="sys_value",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, blank=True, null=True
    )
    content_object = GenericForeignKey("content_type", "object_id")
    is_other = models.BooleanField(default=False)
    range_value = IntegerRangeField(blank=True, null=True)

    class Meta:
        db_table = "sys_value"
        description = "System Values"
