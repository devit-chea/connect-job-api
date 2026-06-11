#!/bin/bash
set -e

CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-4}"
CELERY_POOL="${CELERY_POOL:-threads}"
CELERY_WORKER_TIMEOUT="${CELERY_WORKER_TIMEOUT:-300}"

exec celery -A config worker \
  --loglevel=info \
  --concurrency="$CELERY_CONCURRENCY" \
  --pool="$CELERY_POOL" \
  --time-limit="$CELERY_WORKER_TIMEOUT"
