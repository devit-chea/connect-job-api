#!/bin/bash

set -e

# Set default values if environment variables are not set
GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"
GUNICORN_THREADS="${GUNICORN_THREADS:-2}"

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# echo "Rebuilding Elasticsearch index..."
# python manage.py search_index --rebuild -f

# Seed default pipeline config
echo "Seeding default pipeline config..."
python manage.py default_pipeline_config --code="PIP-00" --is-active --is-default --force-only-default --name="Default Pipeline" --description="Default Pipeline for all company."

# Seed default job category
echo "Seeding default job category..."
python manage.py default_job_categories_config

# Seed default mail template
echo "Seeding default mail template..."
python manage.py insert_mail_template

exec gunicorn config.wsgi \
    --bind 0.0.0.0:8000 \
    --timeout 30 \
    --workers "$GUNICORN_WORKERS" \
    --threads "$GUNICORN_THREADS"
