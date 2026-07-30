#!/bin/bash
set -e

CELERY_POOL="${CELERY_POOL:-threads}"
CELERY_WORKER_TIMEOUT="${CELERY_WORKER_TIMEOUT:-300}"

# ES sync worker: handles index/reindex tasks — can be slow, keep separate
celery -A config worker \
  --queues=es_sync \
  --loglevel=info \
  --concurrency="${CELERY_ES_CONCURRENCY:-2}" \
  --pool="$CELERY_POOL" \
  --time-limit="$CELERY_WORKER_TIMEOUT" \
  --hostname=worker-es@%h &

# Activity worker: high-frequency Redis flush and counter tasks
celery -A config worker \
  --queues=activity \
  --loglevel=info \
  --concurrency="${CELERY_ACTIVITY_CONCURRENCY:-3}" \
  --pool="$CELERY_POOL" \
  --time-limit="$CELERY_WORKER_TIMEOUT" \
  --hostname=worker-activity@%h &

# ERP sync worker: integration tasks (outbound HTTP to WingDigital)
celery -A config worker \
  --queues=erp_sync \
  --loglevel=info \
  --concurrency="${CELERY_ERP_CONCURRENCY:-2}" \
  --pool="$CELERY_POOL" \
  --time-limit="$CELERY_WORKER_TIMEOUT" \
  --hostname=worker-erp@%h &

# Default worker: email, notifications, and everything else
celery -A config worker \
  --queues=celery \
  --loglevel=info \
  --concurrency="${CELERY_CONCURRENCY:-4}" \
  --pool="$CELERY_POOL" \
  --time-limit="$CELERY_WORKER_TIMEOUT" \
  --hostname=worker-default@%h

wait
