from rest_framework import serializers

from apps.auth_oauth.constants.auth_constants import UserTypes


class OperatorIntegrationRecruiterSerializer(serializers.Serializer):
    erp_user_id = serializers.CharField(
        max_length=255,
        help_text="ERP's own user ID — stored in IntegrationUserMapping.partner_user_id.",
    )
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    phone_number = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    role_type = serializers.ChoiceField(
        choices=[
            (UserTypes.ADMIN_RECRUITER.value, "Admin Recruiter"),
            (UserTypes.RECRUITER.value, "Recruiter"),
        ],
        default=UserTypes.ADMIN_RECRUITER.value,
    )
