from django.db import models
from django.db.models import ProtectedError

from apps.core.exceptions.base_exceptions import BadRequestException


class BaseTrackableModel(models.Model):
    """
    Abstract base model for timestamp and user tracking.
    Provides `create_date`, `write_date`, `create_uid`, and `write_uid` fields.
    Overrides the `delete` method to raise a custom exception for protected errors.
    """

    create_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    write_date = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        """
        Overrides the delete method to handle `ProtectedError` exceptions.
        Raises a custom `BadRequestException` if deletion is not allowed.
        """
        try:
            super().delete(using=using, keep_parents=keep_parents)
        except ProtectedError:
            raise BadRequestException("This record cannot be deleted as it contains references to other entities.")
