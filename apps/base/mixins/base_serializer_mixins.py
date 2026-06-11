from rest_framework import serializers


class BaseReadOnlyFieldsMixin:
    """
    Mixin to mark common audit fields as read-only.
    """
    COMMON_READ_ONLY_FIELDS = {
        "id",
        "create_date", "write_date",
        "create_uid", "write_uid",
        "create_ucp_id", "write_ucp_id"
    }

    def get_fields(self):
        fields = super().get_fields()

        model_fields = {f.name for f in self.Meta.model._meta.get_fields()}
        # Add audit fields dynamically if they exist on the model and are missing
        for field_name in self.COMMON_READ_ONLY_FIELDS:
            if field_name in model_fields and field_name not in fields:
                fields[field_name] = serializers.ReadOnlyField()

        # Mark all audit fields as read-only
        for field_name in self.COMMON_READ_ONLY_FIELDS:
            if field_name in fields:
                fields[field_name].read_only = True

        return fields
