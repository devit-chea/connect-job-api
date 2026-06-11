import json
import logging
from datetime import timezone as dt_timezone

from django.conf import settings
from django.utils import timezone

from apps.job_management_app.constants.job_post_types import JobPostStatusTypes

logger = logging.getLogger(__name__)

_TASK_PATH = "job_management_app.publish_scheduled_job_post"


def _task_name(job_post_id: int) -> str:
    return f"publish_job_post_{job_post_id}"


class JobPostScheduleService:

    @staticmethod
    def resolve(post_date, current_post_date=None):
        """
        Called only when recruiter sets status = ACTIVE.
        Determines whether to publish immediately or schedule for later.

        Returns (effective_post_date, effective_status)
        """
        effective_post_date = post_date or current_post_date or timezone.now()

        if effective_post_date.date() > timezone.localdate():
            return effective_post_date, JobPostStatusTypes.SCHEDULED

        return effective_post_date, JobPostStatusTypes.ACTIVE

    @staticmethod
    def schedule_publish(job_post_id: int, publish_at) -> None:
        """
        Register a one-off CrontabSchedule + PeriodicTask that fires
        at the exact minute of publish_at and publishes job_post_id.
            — updates the crontab if the time changed.
        """
        from django_celery_beat.models import CrontabSchedule, PeriodicTask

        if timezone.is_naive(publish_at):
            raise ValueError("publish_at must be timezone-aware.")

        utc_dt = publish_at.astimezone(dt_timezone.utc)

        crontab, _ = CrontabSchedule.objects.get_or_create(
            minute=str(utc_dt.minute),
            hour=str(utc_dt.hour),
            day_of_week="*",
            day_of_month=str(utc_dt.day),
            month_of_year=str(utc_dt.month),
            timezone=settings.TIME_ZONE,
        )

        _, created = PeriodicTask.objects.update_or_create(
            name=_task_name(job_post_id),
            defaults={
                "crontab": crontab,
                "task": _TASK_PATH,
                "kwargs": json.dumps({"job_post_id": job_post_id}),
                "one_off": True,
                "enabled": True,
                "start_time": publish_at,
                "description": f"Auto-publish job post {job_post_id} at {publish_at.isoformat()}",
            },
        )

        logger.info(
            "PeriodicTask '%s' %s — fires at %s UTC",
            _task_name(job_post_id),
            "created" if created else "updated",
            utc_dt.isoformat(),
        )

    @staticmethod
    def cancel_publish(job_post_id: int) -> bool:
        """
        Delete the PeriodicTask for this job (e.g. recruiter changes to DRAFT/INACTIVE).
        Returns True if a task was found and deleted.
        """
        from django_celery_beat.models import PeriodicTask

        deleted, _ = PeriodicTask.objects.filter(name=_task_name(job_post_id)).delete()
        if deleted:
            logger.info("PeriodicTask '%s' deleted.", _task_name(job_post_id))
        return bool(deleted)