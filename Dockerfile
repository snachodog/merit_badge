# syntax=docker/dockerfile:1
ARG TARGETARCH
FROM python:3.12.13-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /srv --shell /usr/sbin/nologin app \
 && mkdir -p /data/media /srv/staticfiles \
 && chown app:app /data/media /srv /srv/staticfiles
WORKDIR /srv
COPY requirements.txt requirements-dev.txt ./

# CSS build stage: Tailwind standalone CLI + DaisyUI plugin. No Node.js, no CDN.
# Versions are pinned and checked by SHA-256. The output is not committed.
FROM scratch AS tailwind-amd64
ADD --checksum=sha256:dc61b3ac6b8c9ca874c0cc4c57b2409791a64c5540404ca5f5367360babc313a --chmod=755 \
    https://github.com/tailwindlabs/tailwindcss/releases/download/v4.3.3/tailwindcss-linux-x64 /tailwindcss
FROM scratch AS tailwind-arm64
ADD --checksum=sha256:55fd0b241214eff3de1e8ee4f22796662f2d2e7a49bcfca7477cfd0bac398195 --chmod=755 \
    https://github.com/tailwindlabs/tailwindcss/releases/download/v4.3.3/tailwindcss-linux-arm64 /tailwindcss
FROM tailwind-${TARGETARCH} AS tailwind

FROM debian:bookworm-slim AS css
COPY --from=tailwind /tailwindcss /usr/local/bin/tailwindcss
ADD --checksum=sha256:f7f7291b67a08abc383b2323055b37aa0bde195a3eaeca6601d766ef0a65231c \
    https://github.com/saadeghi/daisyui/releases/download/v5.7.47/daisyui.js /build/app/frontend/daisyui.js
WORKDIR /build
COPY app/frontend/app.css app/frontend/app.css
COPY app/templates app/templates
RUN tailwindcss --input app/frontend/app.css --output /out/app.css --minify

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
COPY --from=css --chown=app:app /out/app.css ./app/static/css/app.css
COPY --chown=app:app scripts/entrypoint.sh ./scripts/entrypoint.sh
USER app
# Build-time static collection only; the key is not used at runtime.
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput
ENV DJANGO_MEDIA_ROOT=/data/media
EXPOSE 8000
ENTRYPOINT ["/bin/sh", "/srv/scripts/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--chdir", "/srv/app", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
