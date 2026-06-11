from django.db import models

from apps.base.models.company_model import Company


class AbstractBaseCompany(models.Model):

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, blank=True, null=True, editable=False
    )

    class Meta:
        abstract = True


class AbstractReferenceNo(models.Model):
    reference_no = models.CharField(max_length=255, editable=False)

    class Meta:
        abstract = True
