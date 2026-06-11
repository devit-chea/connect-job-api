from rest_framework import serializers

from apps.auth_oauth.models.profile_model import ProfileDocumentModel, Profile
from apps.auth_oauth.utils.auth_util import get_active_profile_id
from apps.base.serializers.base_serializer import BaseAndAuditSerializer


class ProfileDocumentSerializer(BaseAndAuditSerializer):
    profile = serializers.PrimaryKeyRelatedField(
        queryset=Profile.objects.all(), required=False, allow_null=True,
    )
    document_id = serializers.CharField()
    inject_company_id = False
    document_type = serializers.ChoiceField(choices=ProfileDocumentModel.DocumentType.choices)

    class Meta:
        model = ProfileDocumentModel
        fields = [
            "id",
            "profile",
            "document_id",
            "document_type",
            "is_default",
            "status",
        ]

    def to_internal_value(self, data):
        active_profile_id, _ = get_active_profile_id(self.context.get("request", None))
        data["profile"] = active_profile_id
        return super().to_internal_value(data)

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)


class ProfileDocumentLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileDocumentModel
        fields = ["document_id", "document_type"]
        file_mapping_ref_type = "profiledocumentmodel"
