from apps.base.models.abstract_base_model import AbstractBaseModel
from django.db import models

class Language(AbstractBaseModel):
    name = models.CharField(max_length=100,unique=True)
    code = models.CharField(max_length=100)
    iso_code = models.CharField(max_length=100,blank=True,null=True)
    url_code = models.CharField(max_length=200,blank=True,null=True)
    active = models.BooleanField(default=False)

    class Meta:
        db_table = "res_language"
   