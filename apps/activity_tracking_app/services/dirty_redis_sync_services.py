import logging
from django_redis import get_redis_connection

logger = logging.getLogger(__name__)


class DirtyRedisSyncService:
    """
    Tracks dirty job_post_id in Redis. And to be bulk synced to ES asynchronously.
    """
    JOB_POST_SET_KEY = "dirty_job_post_ids"
    # Use the 'default' alias or whichever is configured in your settings.py
    REDIS_ALIAS = "default"

    @classmethod
    def _get_client(cls):
        return get_redis_connection(cls.REDIS_ALIAS)
    
    @classmethod
    def mark_job_post_dirty(cls, job_post_id: int) -> None:
        client = cls._get_client()
        client.sadd(cls.JOB_POST_SET_KEY, job_post_id)

    @classmethod
    def mark_job_posts_dirty(cls, job_post_ids: list[int]) -> None:
        if job_post_ids:
            client = cls._get_client()
            client.sadd(cls.JOB_POST_SET_KEY, *job_post_ids)

    @classmethod
    def pop_dirty_job_post_ids(cls) -> list[int]:
        logger.info("[DirtyRedisSyncService] Start Dirty Job Post task")
        client = cls._get_client()
        
        dirty_ids = client.smembers(cls.JOB_POST_SET_KEY)
        if not dirty_ids:
            logger.info("[DirtyRedisSyncService] No dirty job_post_ids found in Redis")
            return []

        try:
            job_post_ids = list(map(int, dirty_ids))
        except Exception as e:
            logger.error(f"[DirtyRedisSyncService] Failed to parse dirty job post ids: {e}")
            client.delete(cls.JOB_POST_SET_KEY)
            return []

        client.delete(cls.JOB_POST_SET_KEY)
        logger.info(f"[DirtyRedisSyncService] Completed Dirty Job Post task | dirty_ids={dirty_ids}")
        return job_post_ids
