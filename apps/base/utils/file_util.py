import magic
from datetime import datetime
from django.core.files.base import ContentFile
from django.conf import settings
from rest_framework import status
from django.http import Http404, HttpResponse
from django.views.static import serve
from rest_framework.authtoken.models import Token

from apps.base.models.file_model import FileModel
from apps.base.constants.base_constants import FileAccessLevel

from apps.base.serializers.file_serializer import FileSerializer


class FileUtil:
    @classmethod
    def serve_protected_file(cls, request, document_root, path):
        token = request.META.get('HTTP_AUTHORIZATION')
        if token:
            token_parts = token.split()
            token = token_parts[1]
            token_object = Token.objects.filter(key=token).first()
            if token_object and  not token_object.user:
                return HttpResponse("Unauthorized", status=status.HTTP_401_UNAUTHORIZED)
        # Check if the user is authenticated to access the media
        elif not request.user.is_authenticated:
            return HttpResponse("Unauthorized", status=status.HTTP_401_UNAUTHORIZED)
        try:
            return serve(request, path, document_root=settings.MEDIA_ROOT)
        except Http404:
            return HttpResponse("File not found", status=404)


    @classmethod
    def update_or_delete_multiple_file_ref_id(cls, ref_type, ref_id, user_id, files=None, employee_id=None, is_update=None):
        if files is None:
            files = []

        if ref_type and ref_id:
            cls.remove_files(files, ref_id, ref_type)

            file_update = FileModel.objects.filter(
                ref_type=ref_type, ref_id=None, create_uid=user_id
            )
            if is_update:
                file_update.filter(hr_employee=employee_id)
            else:
                file_update.filter(hr_employee=None)

            if files:
                file_update.filter(id__in=files).update(ref_id=ref_id, hr_employee = employee_id)
                return file_update

    @classmethod
    def remove_files(cls, files, ref_type, ref_id):
        delete_files = FileModel.objects.filter(
            ref_type=ref_type, ref_id=ref_id
        ).exclude(pk__in=files,)
        delete_files.delete()

    @classmethod
    def update_multiple_file_ref_id(cls, ref_type, ref_id, user_id, files=None, access_level=FileAccessLevel.PRIVATE):
        if ref_type and ref_id:
            file_update = FileModel.objects.filter(
                ref_type=ref_type, ref_id=None, create_uid=user_id
            )
            if files:
                file_update.filter(id__in=files).update(ref_id=ref_id, access_level=access_level)
                return file_update

    @classmethod
    def count_files(cls, ref_type, ref_id):
        return FileModel.objects.filter(ref_type=ref_type, ref_id=ref_id).count()

    @classmethod
    def create_files(cls, validated_files, ref_id, ref_type, employee):
        files = None
        if validated_files:
            data = validated_files.get("data")
            if data:
                cts = [
                    FileModel(
                        file_type=d.content_type,
                        file_name=d.name,
                        file=d,
                        ref_id=ref_id,
                        ref_type=ref_type,
                        employee=employee,
                    )
                    for d in data
                ]
                files = FileModel.objects.bulk_create(cts)

            return files

    @classmethod
    def update_files(cls, validated_files, ref_id, ref_type, employee):
        files = None
        if validated_files:
            data = validated_files.get("data")
            exited_files = FileModel.objects.filter(
                ref_id=ref_id, ref_type=ref_type, hr_employee=employee
            )
            if exited_files.exists():
                exited_files.delete()
            if data:
                cts = [
                    FileModel(
                        file_type=d.content_type,
                        file_name=d.name,
                        file=d,
                        ref_id=ref_id,
                        ref_type=ref_type,
                        hr_employee=employee,
                    )
                    for d in data
                ]
                files = FileModel.objects.bulk_create(cts)

            return files

    @staticmethod
    def clone_file(original_file_instance, user_instance, employee_instance, new_ref_type=None):
        original_file = original_file_instance.file.read()
        new_file = ContentFile(original_file, name=original_file_instance.file_name)
        new_file.content_type = magic.from_buffer(original_file, mime=True)

        new_file_data = {
            "file": new_file,
            "file_name": original_file_instance.file_name,
            "file_size": original_file_instance.file_size,
            "ref_type": new_ref_type if new_ref_type else original_file_instance.ref_type,
            "file_type": original_file_instance.file_type,
            "create_date": datetime.now(),
            "company": user_instance.base_company.id,
            "hr_employee": employee_instance.id,
        }
        serializer = FileSerializer(
            data=new_file_data, context={"user_id": user_instance.id}
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save()
