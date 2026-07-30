import base64, uuid, six
from django.core.files.base import ContentFile
from rest_framework import serializers
import binascii

from apps.core.exceptions.base_exceptions import BadRequestException


class Base64ImageField(serializers.ImageField):
    BASE64 = ";base64,"

    def to_internal_value(self, data):
        if isinstance(data, six.string_types):
            if not data:
                return None
            if "data:" in data and self.BASE64 in data:
                _, data = data.split(self.BASE64)
            try:
                if isinstance(data, str) and data.lower() == "deleted":
                    return data
                decoded_file = base64.b64decode(data)
            except binascii.Error:
                raise BadRequestException("invalid data base64.")
            file_name = str(uuid.uuid4())
            file_extension = self.get_file_extension(file_name, decoded_file)
            complete_file_name = "%s.%s" % (
                file_name,
                file_extension,
            )
            data = ContentFile(decoded_file, name=complete_file_name)
        else:
            raise BadRequestException("Data type invalid.")
        return super(Base64ImageField, self).to_internal_value(data)

    def get_file_extension(self, file_name, decoded_file):
        # imghdr was removed in Python 3.13; detect image type from magic bytes
        header = decoded_file[:16] if decoded_file else b""
        if header[:3] == b"\xff\xd8\xff":
            extension = "jpg"
        elif header[:8] == b"\x89PNG\r\n\x1a\n":
            extension = "png"
        elif header[:6] in (b"GIF87a", b"GIF89a"):
            extension = "gif"
        elif header[:4] == b"RIFF" and header[8:12] == b"WEBP":
            extension = "webp"
        elif header[:2] in (b"BM",):
            extension = "bmp"
        else:
            extension = "jpg"
        return extension

    def to_representation(self, value):
        from apps.base.models.file_model import FileModel
        from apps.base.serializers.base64_serializer import Base64FileSerializer

        file = FileModel.objects.filter(pk=value).first()
        if not file:
            return
        serializer = Base64FileSerializer(file)
        data = serializer.data
        return data
