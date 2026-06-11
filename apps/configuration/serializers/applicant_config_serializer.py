from apps.base.serializers.base_serializer import BaseSerializer
from apps.configuration.models.applicant_config_model import ApplicantConfig


class ApplicantConfigSerializer(BaseSerializer):

    class Meta:
        model = ApplicantConfig
        fields = "__all__"
