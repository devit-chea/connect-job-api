import base64
import logging
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.serializers.cv_scan_serializer import (
    FileUploadSerializer,
    ProfileCVScanSerializer,
)
from apps.auth_oauth.services.cv_extract_service import CVExtractService
from apps.base.views.base_views import BaseCreateAPIView, BaseUpdateAPIView
from apps.auth_oauth.constants.content_type_constants import FileContentType

logger = logging.getLogger(__name__)


class ProfileCVScanSaveView(BaseCreateAPIView):
    """
    API endpoint to create a user's profile with nested data
    from a CV scan result.
    """

    queryset = Profile.objects.all()
    serializer_class = ProfileCVScanSerializer
    permission_classes = [permissions.IsAuthenticated]


class ProfileCVScanUpdateView(BaseUpdateAPIView):
    """
    API endpoint to update a user's profile with nested data
    from a CV scan result.
    """

    queryset = Profile.objects.all()
    serializer_class = ProfileCVScanSerializer
    permission_classes = [permissions.IsAuthenticated]


class CVExtractAPIView(APIView):
    """
    API endpoint to upload a CV file and extract data via external service.
    """

    @extend_schema(
        summary="Upload and Extract CV Data (PDF Only)",
        description="Receives a **PDF file only** and forwards it to the external service for CV data extraction.",
        request=FileUploadSerializer,
        responses={
            400: {"detail": "file is required"},
            500: {"error": "Failed to forward request to external service: ..."},
        },
    )
    def post(self, request):

        serializer = FileUploadSerializer(data=request.FILES)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        file_obj = request.FILES.get("file")
        content_type = request.POST.get("content_type", FileContentType.BASE64)

        if content_type not in FileContentType.ALL:
            return Response(
                {"error": "Invalid Content Type."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            if content_type == FileContentType.BASE64:
                file_bytes = file_obj.read()
                file_base64 = base64.b64encode(file_bytes).decode("utf-8")
                payload = {"data": file_base64}
            elif content_type == FileContentType.FILE:
                payload = {
                    "Data": (file_obj.name, file_obj.read(), file_obj.content_type)
                }

            extracted_data = CVExtractService.extract(payload, content_type)

        except Exception as exec:
            logger.error(f"CV Extraction failed: {exec}")
            return Response(
                {"error": "CV extraction service is temporarily unavailable."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Handle successful response structure
        if extracted_data is None:
            return Response(
                {"message": "CV extracted successfully, but API returned no content."},
                status=status.HTTP_200_OK,
            )

        # If the API returns a list of dictionaries (e.g., `[{...}]`), extract the dictionary.
        if isinstance(extracted_data, list) and len(extracted_data) > 0:
            final_response_data = extracted_data[0]
        else:
            # Fallback for empty list or if the API unexpectedly changes format
            final_response_data = extracted_data

        return Response(final_response_data, status=status.HTTP_200_OK)
