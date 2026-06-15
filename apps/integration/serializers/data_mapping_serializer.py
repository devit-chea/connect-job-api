from rest_framework import serializers

from apps.integration.models.job_platform import (
    IntegrationFieldMapping,
    IntegrationValueMapping,
)


class IntegrationValueMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationValueMapping
        fields = ["id", "source_value", "target_value", "created_at", "updated_at"]
        extra_kwargs = {
            "id": {"read_only": True},
            "created_at": {"read_only": True},
            "updated_at": {"read_only": True},
        }


class CommaSeparatedTargetValueField(serializers.Field):
    """
    Accepts a list or a comma-separated string on write; always returns a list on read.
    Used for category value mappings where one ConnectJob category maps to multiple ERP labels.
    """

    def to_internal_value(self, data):
        if isinstance(data, list):
            cleaned = [str(v).strip() for v in data if str(v).strip()]
            if not cleaned:
                raise serializers.ValidationError("At least one value is required.")
            return ",".join(cleaned)
        value = str(data).strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value

    def to_representation(self, value):
        if not value:
            return []
        return [v.strip() for v in value.split(",") if v.strip()]


class CategoryValueMappingSerializer(serializers.ModelSerializer):
    """
    Value mapping serializer for the 'category' field.
    target_value accepts a list of ERP category labels on write and returns a list on read.
    Multiple labels are stored as a single comma-separated string in the CharField.
    """

    target_value = CommaSeparatedTargetValueField()

    class Meta:
        model = IntegrationValueMapping
        fields = ["id", "source_value", "target_value", "created_at", "updated_at"]
        extra_kwargs = {
            "id": {"read_only": True},
            "created_at": {"read_only": True},
            "updated_at": {"read_only": True},
        }


class IntegrationValueMappingBulkSerializer(serializers.Serializer):
    """
    Bulk-create multiple ERP values that all map to the same ConnectJob value.

    Example payload:
        {
            "source_value": "Accounting",
            "target_values": ["Finance", "Accounting", "Tax", "Auditor"]
        }

    Every entry in target_values becomes one IntegrationValueMapping row with
    the same source_value — this is the many-to-one pattern.
    """

    source_value = serializers.CharField(max_length=255)
    target_values = serializers.ListField(
        child=serializers.CharField(max_length=255),
        min_length=1,
        help_text="List of ERP values that should all resolve to source_value.",
    )

    def validate_target_values(self, values):
        if len(values) != len(set(values)):
            raise serializers.ValidationError("target_values must not contain duplicates.")
        return values


class IntegrationFieldMappingSerializer(serializers.ModelSerializer):
    """Read serializer — includes nested value_mappings."""

    value_mappings = IntegrationValueMappingSerializer(many=True, read_only=True)

    class Meta:
        model = IntegrationFieldMapping
        fields = [
            "id",
            "source_field",
            "target_field",
            "mapping_type",
            "default_value",
            "is_active",
            "value_mappings",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "created_at": {"read_only": True},
            "updated_at": {"read_only": True},
        }


class IntegrationFieldMappingWriteSerializer(serializers.ModelSerializer):
    """Write serializer — value_mappings are managed via their own endpoints."""

    class Meta:
        model = IntegrationFieldMapping
        fields = [
            "source_field",
            "target_field",
            "mapping_type",
            "default_value",
            "is_active",
        ]

    def validate_source_field(self, value):
        return value.strip().lower()

    def validate_target_field(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        partner = self.context.get("partner")
        source_field = attrs.get("source_field", getattr(self.instance, "source_field", None))

        if partner and source_field:
            qs = IntegrationFieldMapping.objects.filter(
                partner=partner,
                source_field=source_field,
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"source_field": f"A mapping for '{source_field}' already exists."}
                )
        return attrs
