import logging
import os

import requests
from celery import shared_task
from django.core.files.uploadedfile import SimpleUploadedFile
from wdg_storage.serializer import BaseFileUploadSerializer
from wdg_storage.service import FileStorageService

from apps.auth_oauth.models.profile_model import Profile

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    name="mirror_social_image_to_storage.profile",
)
def mirror_social_image_to_storage(self, **kwargs):
    """
    Download the social image (LinkedIn/Google) and save it using FileStorageService.
    Updates profile_picture_id with the resulting file ID.
    """
    profile_id = kwargs.get("profile_id")
    image_url = kwargs.get("image_url")
    try:
        profile = Profile.objects.filter(id=profile_id, profile_picture_id__isnull=True).first()
        logger.warning(f"Finding user profile: {profile}")
        if not profile:
            logger.warning("Profile not found or no social image.")
            return

        response = requests.get(image_url, timeout=10)
        response.raise_for_status()

        # Guess file extension and MIME type
        ext = os.path.splitext(image_url.split("?")[0])[1] or ".jpg"
        content_type = response.headers.get("Content-Type", "image/jpeg")
        filename = (
            f"profile_{profile.first_name.lower()}_{profile.last_name.lower()}{ext}"
        )

        # Wrap in a DRF-compatible UploadedFile
        uploaded_file = SimpleUploadedFile(
            name=filename,
            content=response.content,
            content_type=content_type,
        )
        # Validate with your serializer
        serializer = BaseFileUploadSerializer(data={"file": [uploaded_file]})
        serializer.is_valid(raise_exception=True)
        files = serializer.validated_data["file"]
        if not isinstance(files, (list, tuple)):
            files = [files]

        file_ids = FileStorageService.save_file(files)
        profile.profile_picture_id = file_ids[0]
        profile.save(update_fields=["profile_picture_id"])

        logger.info(f"Profile picture updated {profile_id}")

    except Exception as exc:
        logger.exception("Error while mirroring social image for profile %s", profile_id)
        self.retry(exc=exc, countdown=10)
