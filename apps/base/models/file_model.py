import os, uuid
from django.db import models
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill

from config.settings.base import BASE_DIR

from apps.base.validators.file_validator import FileValidator
from apps.base.models.company_model import Company
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.constants.base_constants import FileAccessLevel, ModelFieldChoices


def upload_directory_path(instance,filename):
    return f"storages/uploads/{filename}"


class FileModel(AbstractBaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(
        db_column="image_url",
        upload_to=upload_directory_path,
        validators=[FileValidator()],
    )
    image_thumbnail = ImageSpecField(
        source="file", processors=[ResizeToFill(100, 100)], options={"quality": 100}
    )
    file_type = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    ref_type = models.CharField(max_length=100, blank=True, null=True)
    ref_id = models.CharField(max_length=100, blank=True, null=True)
    file_name = models.CharField(max_length=250, blank=True, null=True)
    file_size = models.CharField(max_length=250, blank=True, null=True)
    deleted = models.BooleanField(default=False)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, parent_link=True, blank=True, null=True
    )
    # add access level field
    access_level = models.CharField(
        max_length=10,
        choices=ModelFieldChoices.FILE_ACCESS_LEVEL_CHOICES,
        default=FileAccessLevel.PRIVATE,
    )

    class Meta:
        db_table = "files"
        description = "File"

    def delete(self, *args, **kwargs):
        path = os.path.join(BASE_DIR, self.file.name)
        if self.file and os.path.exists(path):
            os.remove(path)
        super(FileModel, self).delete(*args, **kwargs)
