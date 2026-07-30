#FROM python:3.12-slim-bullseye AS base
ARG BASE_DOCKER_IMAGE="python:3.12-slim-bookworm"

FROM ${BASE_DOCKER_IMAGE}

# Set non-interactive mode and update package lists
ARG DEBIAN_FRONTEND=noninteractive
ARG DJANGO_ENV=prod

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Bangkok \
    APP_HOME=/app

USER root

RUN apt-get update  \
    && apt-get install -y --no-install-recommends libmagic1 libpq5 supervisor  \
    && apt-get clean  \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system appuser \
    && adduser --system --ingroup appuser --uid 11000 --home "$APP_HOME" appuser \
    && mkdir -p "$APP_HOME" \
    && chown -R appuser:appuser "$APP_HOME"


WORKDIR $APP_HOME

COPY requirements/ requirements/
COPY static/whl/ static/whl/

RUN pip install --upgrade pip setuptools

# Install Python dependencies
RUN --mount=type=secret,id=pip_conf,dst=/etc/pip.conf \
    if [ "$DJANGO_ENV" = "dev" ]; then \
        pip install --no-cache-dir -r requirements/dev.txt; \
    else \
        pip install --no-cache-dir -r requirements/prod.txt; \
    fi

# Install private WDG packages from local wheels
RUN pip install --no-cache-dir \
    static/whl/wdg_core_file_storage-0.19.12-py3-none-any.whl \
    static/whl/wdg_notification-1.2.0-py3-none-any.whl \
    static/whl/wdg_storages-1.1.7-py3-none-any.whl

COPY apps/ "$APP_HOME"/apps
COPY config/ $APP_HOME/config
COPY static/ $APP_HOME/static
COPY storages/ $APP_HOME/storages
COPY *.py $APP_HOME
COPY *.sh $APP_HOME
COPY *.conf $APP_HOME

RUN mkdir -p /app/staticfiles /app/logs
RUN cp -r /app/static/* /app/staticfiles/

RUN chown -R appuser:appuser "$APP_HOME" && \
    chmod +x /app/entrypoint-*.sh

USER appuser

CMD ["python", "manage.py"]
