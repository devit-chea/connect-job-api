from rest_framework import serializers
from apps.base.serializers.base_serializer import BaseSerializer
from apps.auth_oauth.models.skill_model import Skill
from apps.auth_oauth.utils.auth_util import set_active_profile


class SkillsProfileSerializer(BaseSerializer):
    name = serializers.CharField()

    class Meta:
        model = Skill
        fields = ["id", "name", "description", "user_profile"]
        extra_kwargs = {
            "id": {"read_only": True},
        }

    def to_internal_value(self, data):
        data = set_active_profile(self, data)
        return super().to_internal_value(data)
