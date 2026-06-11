from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers


class ContentTypeMixin:

    def get_contenttype(self, model_name: str):
        content_type = ContentType.objects.filter(model=model_name).first()
        if content_type is None:
            raise serializers.ValidationError({'content_type': ['Model not found for this content_type']})
        return content_type

    def get_content_type(self, **kwargs):
        content_type = ContentType.objects.filter(**kwargs).first()
        if content_type is None:
            raise serializers.ValidationError({'content_type': ['Model not found for this content_type']})
        return content_type

    def get_contenttype_model(self, model_name: str):
        return self.get_contenttype(model_name).model_class()

    def get_model_instance(self, pk, model):
        model_instance = model.objects.filter(id=pk).first()
        if model_instance is None:
            raise serializers.ValidationError({'object_id': ['Model instance not found for this object_id']})
        return model_instance
