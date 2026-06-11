from drf_extra_fields.relations import PresentablePrimaryKeyRelatedField
from rest_framework import serializers

from apps.auth_oauth.constants.auth_constants import LanguageLevels
from apps.auth_oauth.models.profile_language_model import ProfileLanguage, Language
from apps.auth_oauth.utils.auth_util import set_active_profile
from apps.base.serializers.base_serializer import BaseSerializer
from apps.base.serializers.language_serializer import LanguageInfoSerializer


class LanguagesProfileSerializer(BaseSerializer):
    language = PresentablePrimaryKeyRelatedField(
        queryset=Language.objects.all(),
        presentation_serializer=LanguageInfoSerializer,
        required=False,
        allow_null=True,
    )
    level = serializers.ChoiceField(choices=LanguageLevels.choices)
    language_name = serializers.CharField()

    class Meta:
        model = ProfileLanguage
        fields = ["id", "user_profile", "language", "level", "language_name"]
        extra_kwargs = {
            "id": {"read_only": True},
            "user_profile": {"write_only": True},
        }

    def to_internal_value(self, data):
        data = set_active_profile(self, data)
        return super().to_internal_value(data)
