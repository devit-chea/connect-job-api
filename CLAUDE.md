# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ConnectJob API — a Django 5.1 REST API microservice for a job platform (connectkh.com). Built on the WDG Micro Skeleton boilerplate. Core stack: Django + DRF + PostgreSQL + Redis Sentinel + Elasticsearch 7 + Celery.

## Common Commands

```bash
# Local development server
DJANGO_SETTINGS_MODULE=config.settings.dev python manage.py runserver

# Database migrations
python manage.py migrate

# Run tests
python manage.py test
python manage.py test apps.auth_oauth          # single app
python manage.py test apps.auth_oauth.tests    # single file

# Celery worker
celery -A config worker -l info --pool=threads --concurrency=5

# Celery beat scheduler
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Scaffold / remove a new Django app (WDG convention)
python manage.py create app_name
python manage.py destroy app_name

# Useful management commands
python manage.py jwt_keygen                        # generate RS256 key pair
python manage.py create_default_super_admin        # seed superadmin
python manage.py default_pipeline_config           # seed pipeline
python manage.py default_job_categories_config     # seed job categories
python manage.py insert_mail_template              # seed email templates
python manage.py import_institutions               # seed institutions
```

Swagger UI is available at `/swagger/` only when `DJANGO_DEBUG=True`.

## Local Infrastructure

For local development, start the Redis Sentinel cluster + Elasticsearch with:

```bash
cd compose_local
docker compose -f docker-composes-local.yml up -d
```

This starts: redis-master, redis-slave-1/2 (mTLS), sentinel-1/2/3, redisinsight (port 5540), elasticsearch (port 9200).

Copy `.env.example` to `.env` and fill in your values before running the server.

## Architecture

### Settings

Settings are split under `config/settings/`: `base.py` holds all config, `dev.py` and `prod.py` each just `from config.settings.base import *`. Select via `DJANGO_SETTINGS_MODULE`. All settings are driven by env vars read with `environs`.

### App Layout

Each domain lives under `apps/<name>/` following the WDG structure: `models/`, `serializers/`, `views/`, `services/`, `selectors/`, `mixins/`, `tasks/`, `routes/` or `urls.py`.

| App | Responsibility |
|---|---|
| `core` | Pagination, custom exception handler, JWT middleware, sentinel connection factory, base abstract model |
| `base` | Reference/lookup models (Country, Company, Industry, Language, Currency, GeoArea), soft-delete mixin, seeding commands |
| `auth_oauth` | Custom `User` model (`AUTH_USER_MODEL`), RS256 JWT auth with Redis JTI check, social auth pipeline (Google, LinkedIn, Apple, Telegram) |
| `auth_setting` | User auth settings |
| `auth_totp_mail` | TOTP / email-based 2FA |
| `recruiter_management` | Recruiter company profiles |
| `job_management_app` | Job posts, hiring pipelines, applications |
| `activity_tracking_app` | Redis counter-based activity tracking (views, applies) flushed to DB by Celery beat |
| `file_management_app` | File uploads (S3/PowerScale via `wdg-core-file-storage`) |
| `elasticsearch_app` | Elasticsearch document indexing and search (ES 7 / `django-elasticsearch-dsl`) |
| `notification_app` | Notifications via external WDG Notification service |
| `dashboard` | Aggregated dashboard stats |
| `configuration` | System-level config entries |
| `integration` | External connector integrations |

### Key Patterns

**Authentication** — `CustomJWTAuthentication` (RS256) validates the token via SimpleJWT then verifies `access_jti:{jti} == "active"` in Redis. Losing the Redis key immediately revokes access.

**Abstract base models** — `BaseTrackableModel` (`apps/core/abstracts.py`) adds `create_date`/`write_date`. `SoftDeleteModel` (`apps/base/models/soft_delete_model.py`) adds `is_deleted`/`deleted_at` and overrides `delete()` to set the flag instead of issuing a SQL DELETE. Use `Model.objects` (excludes deleted) vs `Model.all_objects`.

**Exceptions** — Use the hierarchy in `apps/core/exceptions/base_exceptions.py`: `BadRequestException`, `NotFoundException`, `UnauthorizedException`, `PermissionDeniedException`, `ExpiredException`. The custom `exception_handler` in `apps/core/exceptions/exception_handler.py` normalises DRF validation errors.

**Pagination** — `CustomPagination` supports `?paging=false` to return a flat list without envelope. Default page size is 10.

**Activity tracking** — Wrap retrieve views with `@track_activity_job_post` (or pass an explicit `ActivityTrackingTypes` value). Failures are logged but never raise.

**Celery beat tasks** (`config/celery.py`) — two periodic tasks flush Redis activity counters to PostgreSQL at configurable intervals (`REDIS_FLUSH_INTERVAL_SECONDS`, `DIRTY_FLUSH_INTERVAL_SECONDS`).

### Redis / Sentinel

Redis is accessed through `django-redis` with `SentinelClient`. The sentinel list is parsed from `REDIS_SENTINELS` (comma-separated `host:port`). mTLS is conditional on `REDIS_SSL=True`. The custom `SentinelConnectionFactory` lives in `apps/core/sentinel.py`.

### URL Structure

All API routes are prefixed with `/api/`. Each app registers its own URLs included from `config/urls.py`. Social OAuth routes live under `/api/auth/` via `drf_social_oauth2`.
