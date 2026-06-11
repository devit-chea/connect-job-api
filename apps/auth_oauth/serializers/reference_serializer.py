from drf_extra_fields.relations import PresentablePrimaryKeyRelatedField
from apps.auth_oauth.models.reference_model import Reference
from apps.auth_oauth.utils.auth_util import set_active_profile
from apps.base.serializers.base_serializer import BaseSerializer
from apps.base.models.company_model import Company
from apps.base.serializers.company_serializer import CompanyLookUpSerializer


class ReferencesProfileSerializer(BaseSerializer):

    company = PresentablePrimaryKeyRelatedField(
        queryset=Company.objects.all(),
        presentation_serializer=CompanyLookUpSerializer,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Reference
        fields = [
            "id",
            "reference_name",
            "job_title",
            "company_name",
            "company",
            "email",
            "phone_number",
            "user_profile",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "reference_name": {"required": True},
            "job_title": {"required": True},
            "email": {"required": True},
            "phone_number": {"required": True},
            "user_profile": {"required": True},
        }

    def to_internal_value(self, data):
        data = set_active_profile(self, data)
        return super().to_internal_value(data)
