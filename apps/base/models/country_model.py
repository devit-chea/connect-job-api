from django.db import models

from apps.base.models.abstract_base_model import AbstractBaseModel


class Country(AbstractBaseModel):
    id = models.IntegerField(primary_key=True)
    code2 = models.CharField(max_length=2, unique=True)
    code3 = models.CharField(max_length=3, unique=True)
    country = models.CharField(max_length=250)
    country_kh = models.CharField(max_length=250, null=True, blank=True)
    nationality = models.CharField(max_length=250)

    class Meta:
        description = "Country"

    def __repr__(self):
        return f"<Country name={self.code2}>"
