import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="job_management_app.publish_scheduled_job_post",
    max_retries=3,
    default_retry_delay=60,
)
def publish_scheduled_job_post(self, job_post_id: int):
    """
    Fires once at the exact scheduled minute (registered by JobPostScheduleService.schedule_publish).
    Publishes a single SCHEDULED job post by setting its status to ACTIVE.
    """
    from apps.job_management_app.constants.job_post_types import JobPostStatusTypes
    from apps.job_management_app.models.job_post_model import JobPostModel

    try:
        updated = JobPostModel.objects.filter(
            pk=job_post_id,
            status=JobPostStatusTypes.SCHEDULED,
            is_deleted=False,
        ).update(status=JobPostStatusTypes.ACTIVE)

        if updated:
            logger.info("Job post %s published successfully.", job_post_id)
        else:
            logger.warning(
                "Job post %s was not published — already active, deleted, or not found.",
                job_post_id,
            )
        return bool(updated)

    except Exception as exc:
        logger.exception("Failed to publish job post %s", job_post_id)
        raise self.retry(exc=exc)
