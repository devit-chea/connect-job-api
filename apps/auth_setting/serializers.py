from .models import AuthSettingModel
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

APP_CHOICES = [
    ("auth_totp_mail", "AUTH TOTP MAIL"),
    ("auth_totp_mfa", "AUTH TOTP MFA")
]
class ToggleAuthSettingSerializers(serializers.Serializer):
    user_id = serializers.IntegerField(write_only=True)
    is_enable = serializers.BooleanField(write_only=True)
    app_name = serializers.ChoiceField(choices=APP_CHOICES, write_only=True)

    class Meta:
        model = AuthSettingModel
        fields = "__all__"

class BulkToggleAuthSettingSerializers(serializers.Serializer):
    is_enable = serializers.BooleanField(write_only=True)
    bulk_user_id = serializers.ListField(allow_empty=False)
    class Meta:
        model = AuthSettingModel
        fields = "__all__"