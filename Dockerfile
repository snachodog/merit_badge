# syntax=docker/dockerfile:1
FROM python:3.12.13-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /srv --shell /usr/sbin/nologin app \
 && mkdir -p /data/media /srv/staticfiles \
 && chown app:app /data/media /srv /srv/staticfiles
WORKDIR /srv
COPY requirements.txt requirements-dev.txt ./

# Test image: `docker compose --profile test run --rm test`
FROM base AS dev
RUN pip install -r requirements-dev.txt
COPY --chown=app:app . .
USER app
CMD ["pytest"]

FROM base AS runtime
RUN pip install -r requirements.txt
COPY --chown=app:app manage.py ./
COPY --chown=app:app app ./app
COPY --chown=app:app scripts/entrypoint.sh ./scripts/entrypoint.sh
USER app
# Build-time static collection only; the key is not used at runtime.
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput
ENV DJANGO_MEDIA_ROOT=/data/media
EXPOSE 8000
ENTRYPOINT ["/bin/sh", "/srv/scripts/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--chdir", "/srv/app", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
