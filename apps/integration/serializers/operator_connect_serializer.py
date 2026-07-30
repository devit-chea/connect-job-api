from rest_framework import serializers


class OperatorConnectSerializer(serializers.Serializer):
    erp_domain = serializers.URLField(
        help_text="Base URL of the Connect ERP instance, e.g. https://erp.example.com"
    )
    company_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="Display name for the auto-created company. Ignored when company_id is supplied.",
    )
    company_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Link an existing ConnectJob company instead of creating a new one.",
    )

    def validate_erp_domain(self, value: str) -> str:
        value = value.rstrip("/")
        if not value.startswith("https://") and not value.startswith("http://"):
            raise serializers.ValidationError("erp_domain must be a valid HTTP/HTTPS URL.")
        return value

    def validate(self, attrs):
        company_id = attrs.get("company_id")
        company_name = attrs.get("company_name", "").strip()
        if not company_id and not company_name:
            raise serializers.ValidationError(
                "Provide either company_id (to link an existing company) "
                "or company_name (to create a new one)."
            )
        return attrs
