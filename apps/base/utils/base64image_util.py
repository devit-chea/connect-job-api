import base64, os
from django.core.files.base import ContentFile

from apps.base.models.file_model import FileModel


class Base64ImageUtil:

    @classmethod
    def create_base64image(cls, validated_file, ref_id, ref_type):
        file_data = {}
        if validated_file:
            file_data["file_type"] = validated_file.content_type
            file_data["file_name"] = validated_file.name
            file_data["file"] = validated_file
            file_data["ref_id"] = ref_id
            file_data["ref_type"] = ref_type
            FileModel.objects.create(**file_data)

    @classmethod
    def update_base64image(cls, validated_file, request_file, ref_id, ref_type):
        queryset_file = FileModel.objects.filter(
            ref_id=ref_id, ref_type=ref_type
        ).first()
        if queryset_file and hasattr(queryset_file, "file"):
            process_update_file(
                validated_file, queryset_file, request_file, ref_id, ref_type
            )
        else:
            cls.create_base64image(validated_file, ref_id, ref_type)


def remove_file(path, old_file, storage):
    if os.path.isfile(path):
        if not old_file.closed:
            old_file.close()
        storage.delete(path)


def process_update_file(validated_file, queryset_file, request_file, ref_id, ref_type):
    if isinstance(validated_file, ContentFile):
        process_update_old_file(
            queryset_file, request_file, validated_file, ref_id, ref_type
        )
    elif isinstance(validated_file, str) and validated_file.lower() == "deleted":
        old_file = queryset_file.file
        storage, path = old_file.storage, old_file.path
        remove_file(path, old_file, storage)
        queryset_file.delete()


def process_update_old_file(
    queryset_file, request_file, validated_file, ref_id, ref_type
):
    old_file = queryset_file.file
    storage, path = old_file.storage, old_file.path
    format_base64 = ";base64,"
    existed_file_encode = base64.b64encode(queryset_file.file.read()).decode("utf-8")
    if "data:" in request_file and format_base64 in request_file:
        _, file_decode = request_file.split(format_base64)
        process_update_old_file_data(
            queryset_file,
            validated_file,
            ref_id,
            ref_type,
            existed_file_encode,
            file_decode,
            path,
            old_file,
            storage,
        )


def process_update_old_file_data(
    queryset_file,
    validated_file,
    ref_id,
    ref_type,
    existed_file_encode,
    file_decode,
    path,
    old_file,
    storage,
):
    if existed_file_encode != file_decode:
        remove_file(path, old_file, storage)
        queryset_file.file_type = validated_file.content_type
        queryset_file.file_name = validated_file.name
        queryset_file.file = validated_file
        queryset_file.ref_id = ref_id
        queryset_file.ref_type = ref_type
        queryset_file.save()
