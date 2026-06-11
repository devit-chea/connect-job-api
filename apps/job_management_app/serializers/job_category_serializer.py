from apps.base.serializers.base_serializer import (
    BaseAndAuditSerializer,
    BaseReadOnlyFieldsSerializer,
)
from apps.base.utils.file_management_util import FileURLService
from apps.job_management_app.models.job_category_model import JobCategoryModel


class JobCategorySerializer(BaseAndAuditSerializer, BaseReadOnlyFieldsSerializer):
    class Meta:
        model = JobCategoryModel
        fields = [
            "id",
            "name",
            "code",
            "description",
            "profile_picture_id",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image"] = presentation.get("profile_image")
        return data
