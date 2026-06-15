# ConnectJob Platform API

SELECT
    -- User
    u.id              AS user_id,
    u.username,
    u.email           AS user_email,
    u.status          AS user_status,
    u.is_active,
    u.phone_number    AS user_phone,

    -- Profile
    p.id              AS profile_id,
    p.full_name,
    p.first_name,
    p.last_name,
    p.email           AS profile_email,
    p.phone_number    AS profile_phone,
    p.gender,
    p.date_of_birth,
    p.current_position,
    p.profile_type,
    p.status          AS profile_status,
    p.is_active       AS profile_is_active,
    p.create_date     AS profile_created_at,

    -- UserCompanyProfile
    ucp.id            AS ucp_id,
    ucp.type          AS ucp_type,
    ucp.status        AS ucp_status,
    ucp.code,
    ucp.provider,
    ucp.state         AS ucp_state,
    ucp.company_id
    
FROM user_company_profile ucp
INNER JOIN auth_oauth_user u  ON u.id  = ucp.user_id
INNER JOIN profile         p  ON p.id  = ucp.profile_id
WHERE p.profile_type = 'applicant'
ORDER BY p.create_date DESC;

Backend REST API for the ConnectJob recruitment platform — built with Django 5, Django REST Framework, PostgreSQL, Redis, Elasticsearch, and Celery.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Local Development (Docker)](#local-development-docker)
- [Local Development (Manual)](#local-development-manual)
- [Environment Variables](#environment-variables)
- [Management Commands](#management-commands)
- [API Documentation](#api-documentation)
- [Integration Feature](#integration-feature)
- [Settings Environments](#settings-environments)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 5.1, Django REST Framework 3.15 |
| Auth | JWT RS256 (SimpleJWT), OAuth2 (Google, LinkedIn, Apple, Telegram) |
| Database | PostgreSQL 14 |
| Cache / Broker | Redis 7 (standalone) or Redis Sentinel (HA) |
| Search | Elasticsearch 8.15 |
| Task Queue | Celery 5, django-celery-beat |
| API Docs | drf-spectacular (Swagger / ReDoc) |
| Container | Docker, Docker Compose |
| Python | 3.12 |

---

## Project Structure

```
.
├── apps/
│   ├── core/                   # Base exceptions, middleware, pagination, sentinel
│   ├── base/                   # Reference models (Company, Country, GeoArea, Language)
│   ├── auth_oauth/             # User model, JWT auth, social auth pipelines
│   ├── auth_setting/           # Auth settings per user
│   ├── auth_totp_mail/         # TOTP / email two-factor auth
│   ├── recruiter_management/   # Recruiter company management
│   ├── job_management_app/     # Job posts, pipelines, applications
│   ├── activity_tracking_app/  # Redis-based view/apply counters → DB flush
│   ├── file_management_app/    # File uploads (S3 / PowerScale)
│   ├── elasticsearch_app/      # Search documents and services
│   ├── notification_app/       # WDG Notification service integration
│   ├── dashboard/              # Aggregated stats
│   ├── configuration/          # System config entries
│   └── integration/            # ConnectJob ↔ WingDigital ERP integration
├── config/
│   ├── settings/
│   │   ├── base.py             # All settings, env-driven
│   │   ├── dev.py              # Dev (imports base)
│   │   ├── prod.py             # Production (imports base)
│   │   └── local.py            # Local Docker dev — standalone Redis, console email
│   ├── celery.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── compose/                    # Dev / UAT / Prod docker-compose files
├── compose_local/              # Local development docker-compose (standalone stack)
│   └── docker-compose.local.yml
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── Dockerfile
├── entrypoint-server.sh        # gunicorn
├── entrypoint-celery.sh        # celery worker
├── entrypoint-celery-beat.sh   # celery beat
└── ConnectJob_Integration.postman_collection.json
```

---

## Local Development (Docker)

The fastest way to get the full stack running locally.

### Prerequisites

- Docker Desktop installed and running
- Private pip registry credentials (for internal `wdg-*` packages)

### Step 1 — Configure pip credentials

```bash
cp compose/secrets/pip.example.conf compose/secrets/pip.conf
# Open compose/secrets/pip.conf and replace USERNAME and PASSWORD
```

### Step 2 — Configure environment

```bash
cp .env.example .env
# The generated .env already has local defaults.
# Required values to verify:
#   DJANGO_SECRET_KEY (already filled)
#   JWT_SIGNING_KEY / JWT_VERIFYING_KEY (already generated)
#   DB_NAME / DB_USER / DB_PASSWORD (defaults: job_platform_local / postgres / postgres)
```

### Step 3 — Build and start

```bash
# Build all images (api, celery, celery-beat)
docker compose -f compose_local/docker-compose.local.yml build

# Start everything
docker compose -f compose_local/docker-compose.local.yml up -d
```

### Step 4 — Initialise the database (first time only)

```bash
# Run migrations
docker compose -f compose_local/docker-compose.local.yml exec api python manage.py migrate

# Seed required data
docker compose -f compose_local/docker-compose.local.yml exec api \
  python manage.py default_pipeline_config \
    --code="PIP-00" --is-active --is-default --force-only-default \
    --name="Default Pipeline" --description="Default Pipeline for all company."

docker compose -f compose_local/docker-compose.local.yml exec api \
  python manage.py default_job_categories_config

docker compose -f compose_local/docker-compose.local.yml exec api \
  python manage.py insert_mail_template

# Create superadmin
docker compose -f compose_local/docker-compose.local.yml exec api \
  python manage.py create_default_super_admin
```

### Service URLs

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/swagger/ |
| ReDoc | http://localhost:8000/redoc/ |
| RedisInsight | http://localhost:5540 |
| PostgreSQL | localhost:5432 |
| Elasticsearch | http://localhost:9200 |

### Useful commands

```bash
# Follow API logs
docker compose -f compose_local/docker-compose.local.yml logs -f api

# Follow Celery logs
docker compose -f compose_local/docker-compose.local.yml logs -f celery

# Run a management command
docker compose -f compose_local/docker-compose.local.yml exec api python manage.py <command>

# Open a Django shell
docker compose -f compose_local/docker-compose.local.yml exec api python manage.py shell

# Stop all services
docker compose -f compose_local/docker-compose.local.yml down

# Stop and wipe all data volumes (full reset)
docker compose -f compose_local/docker-compose.local.yml down -v
```

---

## Local Development (Manual)

If you prefer running Django directly on your machine.

### Prerequisites

- Python 3.12
- PostgreSQL 14
- Redis 7
- Elasticsearch 8.15

Start only the infrastructure services:

```bash
cd compose_local
docker compose -f docker-compose.local.yml up -d postgres redis elasticsearch
```

### Setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows

# Install dev dependencies
pip install -r requirements/dev.txt

# Copy and edit environment file
cp .env.example .env

# Run migrations
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py migrate

# Seed data
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py default_job_categories_config
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py insert_mail_template
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py create_default_super_admin

# Start development server
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py runserver

# Start Celery worker (separate terminal)
DJANGO_SETTINGS_MODULE=config.settings.local \
  celery -A config worker -l info --pool=threads --concurrency=5

# Start Celery beat scheduler (separate terminal)
DJANGO_SETTINGS_MODULE=config.settings.local \
  celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the required values.

| Variable | Description | Local default |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | Settings module to load | `config.settings.local` |
| `DJANGO_SECRET_KEY` | Django secret key | Generated |
| `DB_*` | PostgreSQL connection | `localhost:5432 / postgres` |
| `REDIS_USE_SENTINEL` | `True` = Sentinel, `False` = standalone | `False` |
| `REDIS_URL` | Redis cache URL | `redis://localhost:6379/1` |
| `CELERY_BROKER_URL` | Celery broker URL | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | Celery result backend | `redis://localhost:6379/2` |
| `ES_URLS` | Elasticsearch URL(s) | `http://localhost:9200` |
| `JWT_SIGNING_KEY` | RSA private key (RS256) | Generated |
| `JWT_VERIFYING_KEY` | RSA public key (RS256) | Generated |
| `CONNECTOR_INTEGRATION_KEY` | AES-256 key for ERP integration | Generated |
| `CONNECTOR_INTEGRATION_URL` | WingDigital ERP base URL | `http://localhost:9000` |

For the full list see `.env.example`.

### Generating JWT keys manually

```bash
openssl genrsa -out private.pem 4096
openssl rsa -in private.pem -pubout -out public.pem

# Format for .env (replace newlines with \n)
JWT_SIGNING_KEY=$(awk 'NF {printf "%s\\n",$0}' private.pem)
JWT_VERIFYING_KEY=$(awk 'NF {printf "%s\\n",$0}' public.pem)
```

### Generating the integration encryption key

```bash
python3 -c "import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
# Paste the output into CONNECTOR_INTEGRATION_KEY
```

---

## Management Commands

```bash
# Scaffold a new Django app (WDG convention)
python manage.py create <app_name>

# Remove an existing app
python manage.py destroy <app_name>

# Generate RSA key pair for JWT
python manage.py jwt_keygen

# Create default superadmin user
python manage.py create_default_super_admin

# Seed default pipeline configuration
python manage.py default_pipeline_config \
  --code="PIP-00" --is-active --is-default --force-only-default \
  --name="Default Pipeline" --description="Default Pipeline"

# Seed default job categories
python manage.py default_job_categories_config

# Seed default system values
python manage.py default_sys_values_config

# Seed email templates
python manage.py insert_mail_template

# Import institutions
python manage.py import_institutions

# Load reference data
python manage.py loaddata apps/base/data/factory/countries.json
python manage.py loaddata apps/base/data/factory/res_language.json
```

---

## API Documentation

Swagger UI and ReDoc are available in `DEBUG=True` mode:

- **Swagger UI** — http://localhost:8000/swagger/
- **ReDoc** — http://localhost:8000/redoc/
- **OpenAPI schema** — http://localhost:8000/schema/

All endpoints under `/api/` require a `Bearer <access_token>` header except public endpoints.

A Postman collection covering the full **Integration feature** is available at:

```
ConnectJob_Integration.postman_collection.json
```

Import it into Postman and set the `base_url` and `jwt_token` collection variables to get started.

---

## Integration Feature

ConnectJob integrates bidirectionally with **WingDigital ERP** via a PKCE-based API handshake.

### What it does

| Flow | Direction | Trigger |
|---|---|---|
| Job posting | WingDigital → ConnectJob | ERP calls `POST /api/v1/integration/jobs/publish` |
| Applicant sync | ConnectJob → WingDigital | Applicant submits application |
| Pipeline sync | ConnectJob → WingDigital | Recruiter moves pipeline stage |
| Recruiter sync | ConnectJob → WingDigital | Operator creates recruiter for integrated company |

### Key endpoints

```
POST /api/v1/integration/initialize      Start PKCE handshake
POST /api/v1/integration/exchange        Complete key exchange
POST /api/v1/integration/disconnect      ERP-initiated disconnect
POST /api/v1/integration/jobs/publish    ERP posts a job vacancy
GET  /api/v1/integration/data-mapping    List field mappings
POST /api/v1/integration/data-mapping    Create field mapping
```

### Data mapping

The admin configures field and value mappings in the **Data Mapping** UI so ERP field names (e.g. `position`) are automatically translated to ConnectJob field names (e.g. `title`) when jobs are published. 19 field mappings and 9 job category value mappings are seeded automatically on first connection.

See `project_integration_feature.md` for the full architecture reference.

---

## Settings Environments

| File | Used for | Redis mode |
|---|---|---|
| `config/settings/local.py` | Local Docker / manual dev | Standalone (`DefaultClient`) |
| `config/settings/dev.py` | Dev server (CI / staging) | Controlled by `REDIS_USE_SENTINEL` |
| `config/settings/prod.py` | Production | Sentinel (`SentinelClient`) |

Switch by setting `DJANGO_SETTINGS_MODULE` in your `.env` or shell.

The `REDIS_USE_SENTINEL` flag in `.env` controls whether Django connects to a Redis Sentinel cluster (`True`) or a plain standalone Redis instance (`False`). `local.py` forces it to `False` regardless of the env file.
