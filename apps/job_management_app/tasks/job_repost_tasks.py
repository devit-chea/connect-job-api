import logging
from celery import shared_task
from django.utils import timezone

from apps.job_management_app.constants.job_post_types import JobPostStatusTypes
from apps.job_management_app.models.job_post_model import JobPostModel

logger = logging.getLogger(__name__)


@shared_task
def publish_scheduled_job_post(job_post_id):
    job_post = JobPostModel.objects.filter(id=job_post_id).first()

    if not job_post:
        logger.warning(f"Scheduled publish failed: JobPost {job_post_id} not found.")
        return

    if job_post.status != JobPostStatusTypes.SCHEDULED:
        logger.info(
            f"JobPost {job_post_id} is no longer in SCHEDULED status, skipping."
        )
        return

    job_post.status = JobPostStatusTypes.PUBLISHED
    job_post.save(update_fields=["status"])
    logger.info(f"JobPost {job_post_id} has been published successfully.")
