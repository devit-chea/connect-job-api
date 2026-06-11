from rest_framework import serializers
from apps.base.models.language_model import Language


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = "__all__"


class LanguageInfoSerializer(serializers.ModelSerializer):

    class Meta:
        model = Language
        fields = ["id", "name", "code", "iso_code", "url_code", "active"]
