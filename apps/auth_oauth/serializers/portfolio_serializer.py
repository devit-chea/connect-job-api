from apps.base.serializers.base_serializer import BaseSerializer
from apps.auth_oauth.models.portfolio_model import Portfolio
from apps.auth_oauth.utils.auth_util import set_active_profile


class PortfoliosProfileSerializer(BaseSerializer):

    class Meta:
        model = Portfolio
        fields = ["id", "project_name", "role", "brief_description", "user_profile"]
        extra_kwargs = {
            "id": {"read_only": True},
            "project_name": {"required": True},
            "role": {"required": True},
        }

    def to_internal_value(self, data):
        data = set_active_profile(self, data)
        return super().to_internal_value(data)
