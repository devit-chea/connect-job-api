import base64, uuid, imghdr, six
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
        extension = imghdr.what(file_name, decoded_file)
        extension = "jpg" if extension == "jpeg" else extension

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
