from apps.base.serializers.base_serializer import BaseSerializer
from apps.base.models.institution_model import Institution


class InstitutionSerializer(BaseSerializer):
    class Meta:
        model = Institution
        exclude = ["create_date", "write_date", "create_uid", "write_uid"]


class InstitutionInfoSerializer(BaseSerializer):
    class Meta:
        model = Institution
        fields = ["id", "name", "logo_url", "description"]
