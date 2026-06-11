from rest_framework import serializers

from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.base.serializers.base_serializer import BaseSerializer
from apps.base.utils.file_management_util import FileURLService


class UserCompanyProfileSerializer(BaseSerializer):
    class Meta:
        model = UserCompanyProfile
        fields = "__all__"


class CompanyEmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="profile.full_name", read_only=True)
    email = serializers.EmailField(source="profile.email", read_only=True)
    profile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = UserCompanyProfile
        fields = ["full_name", "email", "type", "status", "profile_image_url", ]

    def get_profile_image_url(self, obj):
        presentation = FileURLService.present_profile_images(obj.profile)
        return (presentation.get("profile_image") or {}).get("file_path")
