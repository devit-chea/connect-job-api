from rest_framework import serializers

from apps.base.models.file_model import FileModel
from apps.base.serializers.base64_serializer import Base64FileSerializer


class FileSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileModel
        file = serializers.ListField(
            child=serializers.FileField(
                max_length=100000, allow_empty_file=False, use_url=False
            )
        )
        fields = "__all__"

        # Define fields for pre-signed url
        file_fields = ["file"]

    def create(self, validated_data):
        validated_data["create_uid"] = self.context["user_id"]
        return super().create(validated_data)

    def get_files_info(self, obj):
        file = FileModel.objects.filter(ref_id=obj.id).all()
        data = None
        if file:
            serializer = Base64FileSerializer(file, many=True)
            data = serializer.data
        return data
