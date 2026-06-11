import logging
from typing import List

from celery import shared_task
from elasticsearch.helpers.actions import bulk
from elasticsearch_dsl.connections import connections

from apps.activity_tracking_app.constants.job_activity_types import ActivityTrackingTypes
from apps.activity_tracking_app.models.job_post_user_activity_count_model import JobPostUserActivityCountModel
from apps.activity_tracking_app.services.dirty_redis_sync_services import DirtyRedisSyncService
from apps.activity_tracking_app.services.redis_flush_services import RedisFlushService
from apps.auth_oauth.services.user_cleanup_service import UserCleanupService
from apps.elasticsearch_app.models.job_post_document import JobPostDocument
from apps.elasticsearch_app.utils import es_utils

logger = logging.getLogger(__name__)

import redis

ACTIVITY_TTL_MAP = {
    ActivityTrackingTypes.VIEW.value: 300,  # 5 minutes
    ActivityTrackingTypes.SAVE.value: 86400,  # 1 day
    ActivityTrackingTypes.APPLY.value: 86400,  # 1 day
}


@shared_task(
    name="activity_tracking.increment_activity",
    autoretry_for=(redis.exceptions.RedisError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5}
)
def increment_activity_in_redis(
        **kwargs
):
    from apps.activity_tracking_app.services.activity_tracking_services import ActivityTrackingServices

    logger.info(
        f"[ActivityTracker] Incrementing activity '{kwargs.get('activity_type')}' for job {kwargs.get('job_post_id')}"
    )
    ActivityTrackingServices.increment(**kwargs)


@shared_task(name="activity_tracking.unsaved_activity")
def unsaved_activity_in_redis(job_post_id, user_company_profile_id):
    from apps.activity_tracking_app.services.activity_tracking_services import ActivityTrackingServices
    logger.info(f"[ActivityTracker] Handling unsaved for job {job_post_id}")
    ActivityTrackingServices.decrease_saved(job_post_id, user_company_profile_id)


@shared_task(
    name="activity_tracking.flush_redis_counters_to_db",
    autoretry_for=(redis.exceptions.RedisError,),
    retry_kwargs={"max_retries": 3, "countdown": 5}
)
def flush_redis_counters_to_db():
    RedisFlushService().handle_flush()


@shared_task(name="activity_tracking.flush_dirty_job_post_ids")
def flush_dirty_job_post_ids():
    dirty_ids = DirtyRedisSyncService.pop_dirty_job_post_ids()
    if dirty_ids:
        bulk_update_job_post_activity_counts_to_es.delay(dirty_ids)


@shared_task(
    name="activity_tracking.bulk_update_job_post_activity_counts_to_es",
    bind=True,
    max_retries=3,
    default_retry_delay=60, )
def bulk_update_job_post_activity_counts_to_es(self, job_post_ids: List[int]):
    """
    Celery task to bulk update job post activity counts in Elasticsearch.
    Args:
        job_post_ids (List[int]): List of job post IDs to update.
        :param job_post_ids: List of job post IDs to update.
        :param self: Celery task instance.
    """

    if not job_post_ids:
        logger.info("[BulkUpdateES] No job post IDs to bulk_update_job_post_activity_counts.")
        return

    client = connections.get_connection()

    try:
        # Retrieve activities counts from all requested job posts in one query
        query_set = JobPostUserActivityCountModel.objects.filter(job_post_id__in=job_post_ids)
        counts = query_set.values('job_post_id', 'view_count', 'save_count', 'apply_count')

        if not counts:
            logger.info(f"[BulkUpdateES] No activity count records found for job_post_ids: {job_post_ids}")
            return

        # Prepare bulk update actions for ES
        actions = [
            {
                "_op_type": "update",
                "_index": es_utils.get_index_name(JobPostDocument),
                "_id": data["job_post_id"],
                "doc": {
                    "view_count": data.get("view_count", 0),
                    "save_count": data.get("save_count", 0),
                    "apply_count": data.get("apply_count", 0),
                },
                "doc_as_upsert": True,
            }
            for data in counts
        ]

        # Bulk update in ES
        success, errors = bulk(client, actions, stats_only=False, raise_on_error=False)

        if errors:
            logger.error(f"Some documents failed to update in Elasticsearch: {errors}")

        logger.info(f"Bulk updated {success} job posts in Elasticsearch")
    except Exception as exc:
        logger.error(f"Exception during bulk ES update: {exc}", exc_info=True)
        # Use exponential backoff retry with max retries
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)


@shared_task(bind=True, max_retries=3, default_retry_delay=10, )
def async_save_job_post(self, user_company_profile_id, job_post_id):
    try:
        from apps.activity_tracking_app.services.activity_tracking_services import save_job_post
        save_job_post(user_company_profile_id, job_post_id)
    except Exception as exc:
        logger.exception(exc)
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3, default_retry_delay=10, )
def async_unsave_job_post(self, user_company_profile_id, job_post_id):
    try:
        from apps.activity_tracking_app.services.activity_tracking_services import unsave_job_post
        unsave_job_post(user_company_profile_id, job_post_id)
    except Exception as exc:
        logger.exception(exc)
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3, default_retry_delay=10, )
def async_apply_job_post(self, user_company_profile_id, job_post_id):
    try:
        from apps.activity_tracking_app.services.activity_tracking_services import apply_job_post
        apply_job_post(user_company_profile_id, job_post_id)
    except Exception as exc:
        logger.exception(exc)
        raise self.retry(exc=exc)

ACTIVITY_TRACKING_TASK_MAP = {
    ActivityTrackingTypes.SAVE.value: async_save_job_post,
    ActivityTrackingTypes.UNSAVE.value: async_unsave_job_post,
    ActivityTrackingTypes.APPLY.value: async_apply_job_post,
}


@shared_task(
    name="cleanup_incomplete_users_task", 
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def cleanup_incomplete_users_task(self):
    try:
        deleted_count = UserCleanupService.cleanup_incomplete_users(
            hours=25,
            hard_delete=False,  # safer
        )

        return f"Cleaned {deleted_count} incomplete users"
    except Exception as exc:
        raise self.retry(exc=exc)