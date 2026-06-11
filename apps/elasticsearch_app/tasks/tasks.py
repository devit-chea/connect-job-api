import logging
from typing import List, Optional

from celery import shared_task

from apps.elasticsearch_app.services.job_post_es_sync_services import JobPostESSyncServices
from apps.job_management_app.constants.job_post_types import JobPostStatusTypes
from apps.job_management_app.models.job_post_model import JobPostModel
from apps.job_management_app.utils.job_post_utils import push_to_dead_letter

logger = logging.getLogger(__name__)


@shared_task(
    name="elastic_task.sync_job_post_to_es",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    acks_late=True,
)
def sync_job_post_to_es(self, *, job_post_id, fields=None, force_delete=False):  # <-- note the *
    """
    Celery task to sync single job post to elasticsearch.
    Args:
        job_post_id (int): The job post id to be synced to elasticsearch.
        fields (Optional[List[str]]): The fields to be synced to elasticsearch.
        force_delete (bool): Whether to force delete the job post from elasticsearch.
    Returns:
        None
    """
    logger.info(f"[Task: SyncJobPostToES] Initiating sync_job_post_to_es for JobPost(id={job_post_id})")
    try:
        job_post = JobPostModel.objects.get(pk=job_post_id)
    except JobPostModel.DoesNotExist:
        logger.error(f"[Task: SyncJobPostToES] JobPost(id={job_post_id}) does not exist in database")
        # Make sure the job post is deleted from elasticsearch
        JobPostESSyncServices.sync_delete(job_post_id)
        return

    try:
        if (
                force_delete
                or job_post.status != JobPostStatusTypes.ACTIVE
                or getattr(job_post, 'is_deleted', False)
        ):
            logger.info(f"[Task: SyncJobPostToES] Soft deleting JobPost(id={job_post_id})")
            JobPostESSyncServices.sync_delete(job_post_id)
        else:
            logger.info(f"[Task: SyncJobPostToES] Partial/Normal Syncing JobPost(id={job_post_id})")
            JobPostESSyncServices.sync(job_post, fields=fields)
    except Exception as e:
        logger.error(f"[Task: SyncJobPostToES] Failed to sync JobPost(id={job_post_id}): {e}")
        push_to_dead_letter(job_post_id, str(e))


@shared_task(
    bind=True,
    name="elastic_task.bulk_sync_job_post_to_es",
    max_retries=3,
    default_retry_delay=60,  # 1 min
    acks_late=True,
)
def bulk_sync_job_post_to_es(
        self,
        job_post_ids: List[int],
        fields: Optional[List[str]] = None,
) -> None:
    if not isinstance(job_post_ids, list):
        logger.error(f"[ES Sync] Expected list for job_post_ids, got {type(job_post_ids).__name__}")
        return

    if fields is not None and not isinstance(fields, list):
        logger.error(f"[ES Sync] Expected list for fields, got {type(fields).__name__}")
        fields = []

    if not job_post_ids:
        logger.warning("[ES Sync] Skipped empty job_post_ids batch.")
        return

    logger.info(f"[ES Sync] Bulk sync triggered for {len(job_post_ids)} job posts.")

    try:
        job_posts = JobPostModel.objects.filter(
            id__in=job_post_ids,
            is_active=True,
            is_deleted=False,
            status=JobPostStatusTypes.ACTIVE
        )

        if not job_posts.exists():
            logger.warning(f"[ES Sync] No active job posts found for: {job_post_ids}")
            return

        # Run sync
        JobPostESSyncServices.bulk_sync(job_posts, fields=fields)

        logger.info(f"[ES Sync] Successfully synced {len(job_post_ids)} job posts.")

    except Exception as e:
        logger.exception(f"[ES Sync] Failed bulk sync for {len(job_post_ids)} job posts.")
        # Push to DLQ individually for fine-grained retry
        for job_post_id in job_post_ids:
            push_to_dead_letter(
                job_post_id=job_post_id,
                error_message=str(e),
            )
        raise self.retry(exc=e)
