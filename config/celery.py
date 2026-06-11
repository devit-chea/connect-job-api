from __future__ import absolute_import, unicode_literals

import os
from datetime import timedelta

from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"config.settings.prod")

app = Celery("app")

# Configure Celery using settings from Django settings.py.
app.config_from_object("django.conf:settings", namespace="CELERY")

app.conf.beat_schedule = {
    "flush-redis-counters-every-interval": {
        "task": "activity_tracking.flush_redis_counters_to_db",
        "schedule": timedelta(seconds=settings.REDIS_FLUSH_INTERVAL_SECONDS),
    },
    "flush-dirty-jobs-post-ids-every-interval": {
        "task": "activity_tracking.flush_dirty_job_post_ids",
        "schedule": timedelta(seconds=settings.DIRTY_FLUSH_INTERVAL_SECONDS),
    },
}

# Load tasks from all registered Django app configs.
app.autodiscover_tasks()
