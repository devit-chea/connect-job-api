from rest_framework import serializers
from apps.base.models.geo_area_model import GeoArea
from apps.base.serializers.base_serializer import BaseSerializer


class GeoAreaViewSerializer(BaseSerializer):
    class Meta:
        model = GeoArea
        fields = "__all__"


class GeoAreaSerializer(BaseSerializer):
    class Meta:
        model = GeoArea
        fields = ["id", "name", "name_kh", "parent_id", "deep_level", "country"]
        extra_kwargs = {
            "id": {"required": False},
            "name": {"required": False},
            "name_kh": {"required": False},
            "parent_id": {"required": False},
            "deep_level": {"required": False},
            "country": {"required": False},
        }


class GeoAreaListSerializer(BaseSerializer):
    class Meta:
        model = GeoArea
        fields = ["id", "name", "name_kh", "parent_id"]


class GeoAreaInfoSerializer(BaseSerializer):
    class Meta:
        model = GeoArea
        fields = ["id", "name", "name_kh", "deep_level", "parent_id"]
