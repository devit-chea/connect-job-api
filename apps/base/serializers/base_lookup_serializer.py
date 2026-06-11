from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType


class ContentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentType
        fields = "__all__"


class BaseLookupSerializer(serializers.Serializer):
    contenttype = serializers.CharField()
    fields = serializers.ListField(child=serializers.CharField())
    mapping = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    paging = serializers.BooleanField(default=False)


class BaseModelSerializer(serializers.Serializer):
    pass
