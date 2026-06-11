from django.db import models
from django.utils import timezone

from apps.base.utils.manager import SoftDeleteManager


class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.deleted_at = timezone.now()

        update_fields = ["is_deleted", "deleted_at"]
        if hasattr(self, "write_uid"):
            update_fields.append("write_uid")
        if hasattr(self, "write_ucp_id"):
            update_fields.append("write_ucp_id")
        # Optional: set status to "Deleted" if the model has it
        # Check if the model actually has a real model field named "status"
        try:
            field = self._meta.get_field("status")
        except Exception:
            field = None

        # Only continue if it's a real CharField with choices
        if field and isinstance(field, models.CharField):
            choices = [c[0] for c in getattr(field, "choices", [])]

            if "DELETED" in choices:
                self.status = "DELETED"
            elif "Deleted" in choices:
                self.status = "Deleted"
            elif choices:
                # fallback to first defined choice — optional
                self.status = choices[0]
            else:
                # no choices, skip
                pass

            update_fields.append("status")

        self.save(update_fields=update_fields)
