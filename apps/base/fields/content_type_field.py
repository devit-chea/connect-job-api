from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers


class ContentTypeModelField(serializers.Field):
    def to_internal_value(self, content_type_model):
        try:
            content_type = ContentType.objects.get(model=content_type_model)
        except ContentType.DoesNotExist:
            raise serializers.ValidationError("Invalid content type.")
        return content_type

    def to_representation(self, value):
        return value.model
