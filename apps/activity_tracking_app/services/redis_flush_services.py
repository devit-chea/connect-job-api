import logging
from typing import List

from django.db import transaction
from django.db.models import F
from django_redis import get_redis_connection

from apps.activity_tracking_app.constants.job_activity_types import ActivityTrackingTypes
from apps.activity_tracking_app.models.job_post_user_activity_count_model import JobPostUserActivityCountModel
from apps.activity_tracking_app.models.job_post_user_event_model import JobPostUserEventModel
from apps.activity_tracking_app.services.dirty_redis_sync_services import DirtyRedisSyncService

logger = logging.getLogger(__name__)

# Maps activity types to model field names for dynamic updates
ACTIVITY_FIELD_MAP = {
    ActivityTrackingTypes.VIEW.value: "view_count",
    ActivityTrackingTypes.SAVE.value: "save_count",
    ActivityTrackingTypes.APPLY.value: "apply_count",
}


class RedisFlushService:
    """
    Service class to flush job activity tracking data from Redis to PostgresSQL.

    - Flushes aggregated counters per job post (view/save/apply).
    - Flushes detailed activity logs from deduplicated Redis keys.
    - Handles malformed keys gracefully and logs warnings.
    - Fault-tolerant: one bad key does not block the whole flush.
    """

    def __init__(self):
        self.redis = get_redis_connection("default",) 
        self.logger = logger

    def handle_flush(self) -> None:
        """Main entry point to flush counters and logs from Redis to DB."""
        logger.info("===[FlushService] Start Redis flush task===")
        self._flush_counters()
        self._flush_dedup_logs()
        logger.info("===[FlushService] Completed Redis flush task===")

    def _flush_counters(self) -> None:
        """
        Flushes aggregated activity counters from Redis to database.
        Each counter is flushed within a separate transaction.
        """
        keys = self.redis.smembers("job_activity_keys")
        if not keys:
            logger.info("[FlushService] No counter keys to flush.")
            return

        flushed_count = 0
        update_job_post_ids = set()
        for key in keys:
            try:
                if isinstance(key, bytes):
                    key = key.decode("utf-8")
                self._process_counter_key(key, update_job_post_ids)
                flushed_count += 1
            except Exception as e:
                logger.error("[FlushCounter] Failed to process key='%s': %s", key, str(e))
                continue

        # After Flush, delete keys from Redis
        logger.info(f"[FlushService] Flushed {flushed_count} counter keys.")
        self._delete_keys(list(keys) + ["job_activity_keys"])

        # Enqueue ES update async task
        DirtyRedisSyncService.mark_job_posts_dirty(list(update_job_post_ids))

    def _process_counter_key(self, key: str, update_job_post_ids: set[int]) -> None:
        """
        Processes a counter key from Redis and updates the corresponding model.
        """
        parts = key.split(":")
        if len(parts) != 3:
            logger.warning(f"[FlushCounter] Invalid counter key format: {key}")
            return

        _, activity_type, job_id_str = parts
        field_name = ACTIVITY_FIELD_MAP.get(activity_type)
        if not field_name:
            logger.warning(f"[FlushCounter] Unknown activity type '{activity_type}' for key {key}")
            return

        try:
            job_id = int(job_id_str)
            update_job_post_ids.add(job_id)
            count = int(self.redis.get(key) or 0)
        except ValueError as e:
            logger.error(f"[FlushCounter] Invalid job_id or count for key '{key}': {e}")
            return

        try:
            with transaction.atomic():
                updated = JobPostUserActivityCountModel.objects.filter(job_post_id=job_id).update(
                    **{field_name: F(field_name) + count}
                )

                if not updated:
                    # Create a new record with the initial count in the right field
                    JobPostUserActivityCountModel.objects.create(
                        job_post_id=job_id,
                        view_count=count if field_name == "view_count" else 0,
                        save_count=count if field_name == "save_count" else 0,
                        apply_count=count if field_name == "apply_count" else 0,
                    )
        except Exception as e:
            logger.warning("[FlushCounter] DB error for job_id=%s: %s", job_id, str(e))

    def _flush_dedup_logs(self) -> None:
        """
        Flushes detailed activity logs from Redis dedup keys into DB.
        Uses bulk_create with ignore_conflicts=True for idempotency.
        """
        keys = self.redis.smembers("job_activity_dedup_keys")
        if not keys:
            logger.info("[FlushService] No dedup log keys to flush.")
            return

        log_entries: List[JobPostUserEventModel] = []
        for key in keys:
            try:
                if isinstance(key, bytes):
                    key = key.decode("utf-8")
                entry = self._build_log_entry_from_key(key)
                if entry:
                    log_entries.append(entry)
            except Exception as e:
                logger.warning(f"[FlushLog] Malformed dedup key: '{key}' - {e}")
                continue

        if log_entries:
            try:
                JobPostUserEventModel.objects.bulk_create(log_entries, ignore_conflicts=True)
                logger.info(f"[FlushService] Flushed {len(log_entries)} dedup log entries.")
            except Exception as e:
                logger.error(f"[FlushLog] Failed to bulk create activity logs: {e}")

        self._delete_keys(list(keys) + ["job_activity_dedup_keys"])

    def _build_log_entry_from_key(self, key: str) -> JobPostUserEventModel | None:
        """Parses a dedup key into a UserJobActivityModel entry."""
        parts = key.split(":")
        if len(parts) != 4:
            logger.warning(f"[FlushLog] Invalid dedup key format: {key}")
            return None
        _, user_company_profile_id_str, activity_type, job_post_id_str = parts
        try:
            return JobPostUserEventModel(
                user_company_profile_id=int(user_company_profile_id_str),
                job_post_id=int(job_post_id_str),
                activity_type=activity_type,
            )
        except ValueError as e:
            logger.warning(f"[FlushLog] Invalid user/job values in key '{key}': {e}")
            return None

    def _delete_keys(self, keys: list[str]) -> None:
        """Deletes a list of keys from Redis."""
        try:
            self.redis.delete(*keys)
        except Exception as e:
            logger.error(f"[FlushLog] Failed to delete keys: {e}")
