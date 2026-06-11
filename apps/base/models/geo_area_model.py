from django.db import models
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.country_model import Country


class GeoArea(AbstractBaseModel):
    id = models.IntegerField(primary_key=True)  
    name = models.CharField(max_length=255)
    name_kh = models.CharField(max_length=255)
    parent_id = models.IntegerField(null=True, blank=True)
    deep_level = models.IntegerField(null=True, blank=True)
    country = models.ForeignKey(Country, on_delete=models.CASCADE)

    class Meta:
        description = "GeoArea"

    def __repr__(self):
        return f"<Area name={self.name}>"
