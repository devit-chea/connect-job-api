from rest_framework import serializers

from apps.base.models.sys_setting_model import SysSetting
from apps.base.validators.base_unique_together_validator import BaseUniqueTogetherValidator


class SysSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SysSetting
        fields = [
            'id',
            'name',
            'value',
            'description',
            'company',
        ]
        extra_kwargs = {'id': {'read_only': True}}
        validators = [
            BaseUniqueTogetherValidator(
                queryset=SysSetting.objects.all(),
                fields={
                    "name": "",
                },
                is_current_company=True,
            ),
        ]
