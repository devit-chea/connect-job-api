from django.db import models

from apps.core.abstracts import BaseTrackableModel


class AbstractBaseModel(BaseTrackableModel):
    create_uid = models.IntegerField(blank=True, null=True, editable=False)
    write_uid = models.IntegerField(blank=True, null=True, editable=False)
    create_ucp_id= models.CharField(blank=True, null=True, editable=False)
    write_ucp_id = models.CharField(blank=True, null=True, editable=False)

    class Meta:
        abstract = True

    @property
    def _reference_no(self):
        if hasattr(self._meta, "sequence_numbering") and hasattr(
            self, self._meta.sequence_numbering
        ):
            return getattr(self, self._meta.sequence_numbering)