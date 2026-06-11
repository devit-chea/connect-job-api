import magic
from os.path import splitext
from ast import literal_eval
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.template.defaultfilters import filesizeformat
from django.utils.deconstruct import deconstructible

from apps.base.views.sys_setting_view import SysSettingViewByName


@deconstructible
class FileValidator:
    def __init__(self, *args, **kwargs):
        self.allowed_extensions = kwargs.pop("allowed_extensions", None)
        self.max_size = kwargs.pop("max_size", None)

    extension_message = _(
        "Extension '%(extension)s'is not allowed. Allowed extensions are: '%(allowed_extensions)s'."
    )
    max_size_message = _(
        "The current file %(size)s, which is too large. The maximum file size is %(allowed_size)s."
    )
    mime_message = _("The current file type %(mimetype)s, not match with file.")

    def __call__(self, value):
        if not self.allowed_extensions:
            allowed_extensions = SysSettingViewByName.get_setting(
                self, "ALLOWED_EXTENSIONS"
            )
            self.allowed_extensions = literal_eval(allowed_extensions)
        if not self.max_size:
            max_size = SysSettingViewByName.get_setting(
                self, "FILE_MAX_SIZE"
            )  # max_size as MB
            self.max_size = int(max_size) * 1024 * 1024

        ext = splitext(value.name)[1][1:].lower()
        if self.allowed_extensions and ext not in self.allowed_extensions:
            message = self.extension_message % {
                "extension": ext,
                "allowed_extensions": ", ".join(self.allowed_extensions),
            }
            raise ValidationError(message)

        filesize = value.size
        if self.max_size and filesize > self.max_size:
            message = self.max_size_message % {
                "size": filesizeformat(filesize),
                "allowed_size": filesizeformat(self.max_size),
            }

            raise ValidationError(message)
        file = value.file
        if file:
            file.seek(0)
            f = file.read()
            mimetype = magic.from_buffer(f, mime=True)
            if value.content_type != mimetype:
                message = self.mime_message % {
                    "mimetype": mimetype,
                }
                raise ValidationError(message)
