import json
from typing import Optional

from django_celery_beat.models import (
    PeriodicTask,
    IntervalSchedule,
    CrontabSchedule,
)


class CeleryBeatService:
    """
    Reusable service to manage django-celery-beat periodic tasks
    """

    @staticmethod
    def upsert_interval_task(
        *,
        name: str,
        task: str,
        every: int,
        period: str,
        args: Optional[list] = None,
        kwargs: Optional[dict] = None,
        enabled: bool = True,
    ) -> PeriodicTask:
        """
        Create or update interval-based periodic task
        """

        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=every,
            period=period,
        )

        periodic_task, _ = PeriodicTask.objects.update_or_create(
            name=name,
            defaults={
                "interval": schedule,
                "task": task,
                "args": json.dumps(args or []),
                "kwargs": json.dumps(kwargs or {}),
                "enabled": enabled,
            },
        )

        return periodic_task

    @staticmethod
    def upsert_crontab_task(
        *,
        name: str,
        task: str,
        minute: str = "*",
        hour: str = "*",
        day_of_week: str = "*",
        day_of_month: str = "*",
        month_of_year: str = "*",
        args: Optional[list] = None,
        kwargs: Optional[dict] = None,
        enabled: bool = True,
    ) -> PeriodicTask:
        """
        Create or update crontab-based periodic task
        """

        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=minute,
            hour=hour,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            month_of_year=month_of_year,
        )

        periodic_task, _ = PeriodicTask.objects.update_or_create(
            name=name,
            defaults={
                "crontab": schedule,
                "task": task,
                "args": json.dumps(args or []),
                "kwargs": json.dumps(kwargs or {}),
                "enabled": enabled,
            },
        )

        return periodic_task

    @staticmethod
    def disable_task(name: str):
        PeriodicTask.objects.filter(name=name).update(enabled=False)

    @staticmethod
    def enable_task(name: str):
        PeriodicTask.objects.filter(name=name).update(enabled=True)

    @staticmethod
    def delete_task(name: str):
        PeriodicTask.objects.filter(name=name).delete()
