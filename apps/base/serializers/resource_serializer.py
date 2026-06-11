from apps.base.serializers.base_serializer import BaseSerializer
from apps.base.models.language_model import Language


class LanguageSerializer(BaseSerializer):
    class Meta:
        model = Language
        fields = "__all__"
        extra_kwargs = {"name": {"required": False}, "code": {"required": False}}


class LanguageInfoSerializer(BaseSerializer):
    class Meta:
        model = Language
        fields = ["id", "name", "code"]
