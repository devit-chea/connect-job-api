from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from drf_writable_nested import WritableNestedModelSerializer

from apps.base.fields.integer_range_field import IntegerRangeField

# from drf_extra_fields.fields import IntegerRangeField


from apps.base.fields.content_type_field import ContentTypeModelField
from apps.base.models.sys_value_model import SysValue, SysValueCategories
from apps.base.serializers.base_serializer import BaseSerializer
from apps.base.mixins.context_type_mixin import ContentTypeMixin
from drf_spectacular.extensions import OpenApiSerializerFieldExtension


class IntegerRangeFieldExtension(OpenApiSerializerFieldExtension):
    target_class = "apps.base.fields.integer_range_field.IntegerRangeField"

    def map_serializer_field(self, auto_schema, direction):
        return {
            "type": "object",
            "properties": {
                "lower": {"type": "integer"},
                "upper": {"type": "integer"},
            },
        }


class SysValueSerializer(BaseSerializer, ContentTypeMixin):

    object_id_info = serializers.SerializerMethodField()
    content_type = ContentTypeModelField(required=False, allow_null=True)
    range_value = IntegerRangeField(required=False, allow_null=True)

    class Meta:
        model = SysValue
        exclude = ["write_date", "create_uid", "write_uid"]

    def get_object_id_info(self, instance):
        return (
            {
                "id": instance.content_object.id,
                "name": instance.content_object.name,
            }
            if getattr(instance, "content_object")
            else None
        )

    def validate(self, attrs):
        content_type = attrs.get("content_type")
        object_id = attrs.get("object_id")
        if content_type and object_id:
            self.get_model_instance(pk=object_id, model=content_type.model_class())
        elif content_type or object_id:
            raise serializers.ValidationError(
                "Both content_type and object_id must be provided."
            )

        return attrs


class SysValueInfoSerializer(BaseSerializer):
    class Meta:
        model = SysValue
        fields = ["id", "name"]


class SysValueCategoriesSerializer(
    WritableNestedModelSerializer, serializers.ModelSerializer
):
    sys_value = serializers.SerializerMethodField(read_only=True)
    name = serializers.CharField(help_text=_("gender,marital_status"))

    class Meta:
        model = SysValueCategories
        extra_kwargs = {
            "name": {"required": False},
            "module": {"required": False},
            "sys_value": {"required": False},
        }
        fields = "__all__"

    def get_sys_value(self, obj):
        data = None
        sys_value_instance = SysValue.objects.filter(
            category__id=obj.id, company=self.context["request"].user.base_company
        ).exclude(is_other=True)
        serializer = SysValueSerializer(sys_value_instance, many=True)
        if sys_value_instance:
            data = serializer.data
        return data


class SysValueOtherSerializer(BaseSerializer):
    class Meta:
        model = SysValue
        exclude = ["create_uid", "create_date", "write_uid", "write_date"]
        extra_kwargs = {"category": {"required": True}}

    def save(self, **kwargs):
        kwargs["create_uid"] = self.context["request"].user.id
        kwargs["company_id"] = self.context["request"].user.base_company_id
        return super().save(**kwargs)
