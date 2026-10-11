# Merit Badge - personal achievement and learning platform

A private, self-hosted, browser-based platform for working through Scouting-style
requirements and custom achievements. It records personal learning only and does
**not** confer official Scouting America (or any other organization's) awards.
See `PLAN.md` for the full specification. This repository currently implements
**Phase 1** (generic program and requirement engine) on top of the Phase 0 foundation:
login, a health check, a catalog with search, nested requirement display, manual
authoring of custom programs, and JSON import.

Stack: Django 5.2 LTS, PostgreSQL 16, gunicorn, WhiteNoise, Docker Compose.
No external services, analytics, or telemetry.

## Quick start

Requires Docker with the Compose plugin.

```sh
cp .env.example .env
# Edit .env: set DJANGO_SECRET_KEY and POSTGRES_PASSWORD (see comments in file).
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # for the secret key

docker compose up -d --build
curl http://127.0.0.1:8000/healthz        # {"status": "ok"}
```

Open <http://127.0.0.1:8000/> (port set by `WEB_PORT`, interface by `WEB_BIND`;
default is loopback only). Migrations run automatically on every web start.
Set `POSTGRES_PASSWORD` before the first start: it is stored in the database volume.

## First user (bootstrap)

Public registration is disabled; accounts are created by an administrator.
Create the first superuser with either method:

```sh
# Interactive
docker compose run --rm web python manage.py createsuperuser

# Non-interactive, idempotent (does nothing if the user exists)
docker compose run --rm \
  -e BOOTSTRAP_ADMIN_USERNAME=me -e BOOTSTRAP_ADMIN_PASSWORD='choose-a-long-password' \
  web python manage.py bootstrap_admin
```

Then log in at `/accounts/login/`. Further users can be added in the Django admin
at `/admin/`. Avoid leaving `BOOTSTRAP_ADMIN_PASSWORD` in `.env` after use.

## Start, stop, recreate

```sh
docker compose up -d            # start
docker compose stop             # stop, keep containers
docker compose down             # remove containers + network; DATA IS KEPT
docker compose up -d            # recreate; data persists in named volumes
docker compose logs -f web
docker compose ps               # both services should be "healthy"
```

Data lives in two named volumes: `meritbadge_pgdata` (database) and
`meritbadge_media` (evidence/uploads). **`docker compose down -v` deletes them.**
Never run it unless you intend to destroy all data.

## Reverse proxy / HTTPS

The app listens on plain HTTP; terminate TLS at your reverse proxy (nginx, Caddy,
Traefik, ...) and forward to `WEB_BIND:WEB_PORT`. Proxy requirements:

- Pass `Host` and set `X-Forwarded-Proto: https` (overwrite any client-supplied value).
- In `.env`: add the public hostname to `DJANGO_ALLOWED_HOSTS`, the full origin
  (e.g. `https://merit.example.com`) to `DJANGO_CSRF_TRUSTED_ORIGINS`, and set
  `DJANGO_SECURE_COOKIES=true` and `DJANGO_TRUST_PROXY_SSL_HEADER=true`.
- Optionally set `DJANGO_HSTS_SECONDS` (or set HSTS at the proxy).
- Keep `WEB_BIND=127.0.0.1` when the proxy runs on the same host. Do not expose
  the app port to untrusted networks without TLS.
- PostgreSQL is never published to the host.
- Private evidence files must never be served directly by the proxy from the media volume.

## Upgrading

```sh
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup.sql   # see docs/operations.md
git pull
docker compose up -d --build     # rebuilds image; entrypoint applies migrations
docker compose ps
```

Dependency versions are pinned in `requirements.txt`; review and bump deliberately.
Roll back by checking out the previous revision and restoring the backup if a
migration changed the schema. See `docs/operations.md`.

## Tests

Tests use pytest-django against PostgreSQL (a throwaway test database is created):

```sh
docker compose --profile test run --rm --build test
```

## Using the catalog and authoring

After login, use the top navigation.

- **Catalog** (`/catalog/`) lists programs, awards and versions. Search covers names,
  descriptions and requirement text. Each version shows its status and its content-review
  and rights labels. "Unverified" means nobody has checked the wording against its source.
- **A version page** shows the requirement tree with numbers, how each group is completed
  (all, any, choose N, in order, conditional), action tags, and whether the text is
  "Official text" or not.
- **New custom program** creates a program, then an award, then a draft version.
  On the draft's edit page you can add top-level or child requirements, edit, move up or down,
  and delete. Submit the draft for review, then publish. Publishing lists every problem found.
  A published version cannot be edited. Use "Create a draft revision" to correct it.

## Import from JSON

The format is `docs/schemas/program-import.schema.json` (version 1.0). A small custom
example is `docs/schemas/examples/custom-example.json`. It is not official content.

- Imports always create a **draft** version. They never change a published, archived or
  in-review version. A conflict is reported instead.
- Repeating an import with the same `import_key` and content does nothing. The same key with
  changed content replaces the requirements of the still-draft version.
- Official-source text needs a source and a rights status, or the version must be marked `unverified`.
- Files over 1 MiB, 2000 requirements, or 8 levels of nesting are refused.

In the browser, open **Import JSON**, upload the file, read the dry-run report, then choose
"Import as draft". On the command line (the `docs` folder is not in the image, so mount it):

```sh
docker compose run --rm -v "$PWD/docs:/docs:ro" web \
  python manage.py import_program /docs/schemas/examples/custom-example.json --dry-run
docker compose run --rm -v "$PWD/docs:/docs:ro" web \
  python manage.py import_program /docs/schemas/examples/custom-example.json
```

Errors name the place in the file, such as `requirements[2].children[0].text`.
The importer stores `evidence_expectations` (a list of short text labels) on each requirement. It accepts `constraints` (from `PLAN.md` 14.3) but does not store it yet.

## Layout

`app/programs` and `app/requirements` (models, services, views, importer), `app/config` Django project (settings, urls, `core` health/home views and the
`bootstrap_admin` command), `app/templates`, `tests/`, `docs/` (operations and
`decisions/` ADRs), `scripts/entrypoint.sh`, `compose.yaml`, `Dockerfile`.
