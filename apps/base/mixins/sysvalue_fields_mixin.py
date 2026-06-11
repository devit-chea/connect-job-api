from rest_framework import serializers
from drf_extra_fields.relations import PresentablePrimaryKeyRelatedField

from apps.base.models.sys_value_model import SysValue
from apps.base.serializers.sys_value_serializer import SysValueInfoSerializer


class SysValueFieldMixin:
    """
    Mixin to provide a helper for defining SysValue-based fields
    using PresentablePrimaryKeyRelatedField.
    """

    sysvalue_field_kwargs = {
        "queryset": SysValue.objects.all(),
        "presentation_serializer": SysValueInfoSerializer,
        "required": True,
        "allow_null": False,
    }

    @classmethod
    def sysvalue_field(cls, **overrides):
        """
        Shortcut to create a SysValue PresentablePrimaryKeyRelatedField
        with default configuration.
        """
        return PresentablePrimaryKeyRelatedField(
            **{**cls.sysvalue_field_kwargs, **overrides}
        )
