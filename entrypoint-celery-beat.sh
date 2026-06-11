#!/bin/sh
set -e

exec celery -A config beat -l info \
  --scheduler django_celery_beat.schedulers:DatabaseScheduler \
  --max-interval 10
