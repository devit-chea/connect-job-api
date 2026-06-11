from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.base.mixins.custom_jwt_request_mixin import CustomJWTRequestMixin
from apps.base.mixins.permission_mixin import PermissionMixin
from apps.job_management_app.models.job_post_model import JobPostModel
from apps.job_management_app.serializers.job_post_serializer import (
    JobPostSerializer,
)
from apps.job_management_app.serializers.job_repost_serializer import (
    JobPostRepostSerializer,
)


class JobPostRepostView(CustomJWTRequestMixin, PermissionMixin, APIView):
    permission_classes = [IsAuthenticated]
    permission_codename = [
        "admin_recruiter_manage_job_post",
        "recruiter_manage_job_post",
    ]

    def post(self, request, job_post_id):
        original = get_object_or_404(JobPostModel, id=job_post_id)

        serializer = JobPostRepostSerializer(
            data=request.data, context={"request": request, "original": original}
        )
        serializer.is_valid(raise_exception=True)
        new_job_post = serializer.save()

        return Response(
            JobPostSerializer(new_job_post).data, status=status.HTTP_201_CREATED
        )
