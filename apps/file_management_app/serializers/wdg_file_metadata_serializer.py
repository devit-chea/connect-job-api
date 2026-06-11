import uuid

from rest_framework import serializers
from wdg_storage.base import WdgStorageMixin


class WdgStorageBaseSerializer(WdgStorageMixin, serializers.ModelSerializer):
    """
    Base serializer for handling file metadata.

    Only the following fields are considered file references:
    - document_id
    - profile_picture_id
    - cover_picture_id
    """

    FILE_FIELDS = (
        "document_id",
        "profile_picture_id",
        "cover_picture_id",
    )
    file_delete = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
    )

    def _collect_file_ids(self, instance):
        file_ids = []

        for field_name in self.FILE_FIELDS:
            if not hasattr(instance, field_name):
                continue

            value = getattr(instance, field_name)

            if isinstance(value, uuid.UUID):
                file_ids.append(str(value))
            elif isinstance(value, str) and value.strip():
                file_ids.append(value)

        return file_ids

    def _extract_file_fields(self, validated_data):
        return validated_data.pop("file_delete", [])

    def _update_file_metadata(self, instance):
        file_ids = self._collect_file_ids(instance)
        if not file_ids:
            return

        files_data = [
            {
                "file_id": file_id,
                "is_success": True,
                "instance": instance,
            }
            for file_id in file_ids
        ]
        self.update_metadata(files_data)

    def create(self, validated_data):
        delete_files = self._extract_file_fields(validated_data)
        instance = super().create(validated_data)
        if delete_files:
            self.delete_files(file_id=delete_files)

        self._update_file_metadata(instance)
        return instance

    def update(self, instance, validated_data):
        delete_files = self._extract_file_fields(validated_data)

        instance = super().update(instance, validated_data)

        if delete_files:
            self.delete_files(file_id=delete_files)
        self._update_file_metadata(instance)
        return instance
