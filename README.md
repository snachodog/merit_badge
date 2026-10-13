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
The easy way: set `BOOTSTRAP_ADMIN_USERNAME` and `BOOTSTRAP_ADMIN_PASSWORD` in `.env`.
The web container creates that user each time it starts, if the user does not exist yet.
Remove the password from `.env` afterwards.

You can also create the first superuser by hand with either method:

```sh
# Interactive
docker compose run --rm web python manage.py createsuperuser

# Non-interactive, idempotent (does nothing if the user exists)
docker compose run --rm \
  -e BOOTSTRAP_ADMIN_USERNAME=me -e BOOTSTRAP_ADMIN_PASSWORD='choose-a-long-password' \
  web python manage.py bootstrap_admin
```

If the user already exists, the command does not change the password. To set a new one, add
`--reset-password` to the command.

Then log in at `/accounts/login/`. The first user is an admin. Admins manage users under
Settings, Users: role, deactivate, reactivate and password reset. At least one active admin must
always remain. Each user authors only their own programs, which stay private. Admins can share a
program with chosen users or all users on its page. You can also add users in the Django admin
at `/admin/`. Avoid leaving `BOOTSTRAP_ADMIN_PASSWORD` in `.env` after use.

## Run from the published image

You do not need to clone this repository to run the app. Pull the image from Docker Hub
instead. Two ready-made files sit at the top of the repo: `sample.docker-compose.yaml` and
`sample.env`.

1. Make an empty folder and copy in `sample.docker-compose.yaml` as `docker-compose.yaml`
   and `sample.env` as `.env`.
2. Edit `.env`. Set `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD`. Set `MERIT_BADGE_VERSION`
   to a release such as `0.4.0`. Use `main` until the first image release exists.
3. Run `docker compose up -d`.
4. Create your first user. See [First user](#first-user-bootstrap).

Both files below work with the same `.env`. The minimal file needs only the two required
values. The robust file uses every setting in `.env`.

### Minimal `docker-compose.yaml`

The smallest working setup. It binds to `127.0.0.1` only and has no hardening beyond that.

```yaml
services:
  db:
    image: postgres:16.10-bookworm
    restart: unless-stopped
    environment:
      POSTGRES_DB: meritbadge
      POSTGRES_USER: meritbadge
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD in .env}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U meritbadge -d meritbadge"]
      interval: 5s
      retries: 20

  web:
    image: dogiakos/merit_badge:latest
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY:?set DJANGO_SECRET_KEY in .env}
      POSTGRES_HOST: db
      POSTGRES_DB: meritbadge
      POSTGRES_USER: meritbadge
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD in .env}
    volumes:
      - media:/data/media
    ports:
      - "127.0.0.1:8000:8000"

volumes:
  pgdata:
  media:
```

### Robust `docker-compose.yaml`

Use this for a server you leave running. It adds these protections:

- **Private database:** PostgreSQL sits on an internal network and publishes no port.
- **Health checks:** each service has one, and the web service waits for a healthy database.
- **Locked-down web container:** read-only filesystem, all capabilities dropped, no new privileges.
- **Limits:** memory and process caps, and rotated logs.
- **Settings:** everything in `.env` (HTTPS, proxy, upload size, first user) is passed through.

This text is the same as `sample.docker-compose.yaml`. A test checks that the two match.

```yaml
# Robust deployment using the published image. Copy to docker-compose.yaml
# and copy sample.env to .env, then edit .env. See README.md.
name: meritbadge

services:
  db:
    image: postgres:16.10-bookworm
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-meritbadge}
      POSTGRES_USER: ${POSTGRES_USER:-meritbadge}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD in .env}
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks: [backend]            # no "ports:" and an internal network: PostgreSQL is never exposed
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 20
      start_period: 10s
    mem_limit: 512m
    pids_limit: 200
    logging:
      driver: json-file
      options: {max-size: "10m", max-file: "3"}

  web:
    image: ${MERIT_BADGE_IMAGE:-dogiakos/merit_badge}:${MERIT_BADGE_VERSION:-latest}
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY:?set DJANGO_SECRET_KEY in .env}
      DJANGO_DEBUG: "false"
      DJANGO_ALLOWED_HOSTS: ${DJANGO_ALLOWED_HOSTS:-localhost,127.0.0.1}
      DJANGO_CSRF_TRUSTED_ORIGINS: ${DJANGO_CSRF_TRUSTED_ORIGINS:-}
      DJANGO_SECURE_COOKIES: ${DJANGO_SECURE_COOKIES:-false}
      DJANGO_TRUST_PROXY_SSL_HEADER: ${DJANGO_TRUST_PROXY_SSL_HEADER:-false}
      DJANGO_HSTS_SECONDS: ${DJANGO_HSTS_SECONDS:-0}
      POSTGRES_HOST: db
      POSTGRES_DB: ${POSTGRES_DB:-meritbadge}
      POSTGRES_USER: ${POSTGRES_USER:-meritbadge}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD in .env}
      BOOTSTRAP_ADMIN_USERNAME: ${BOOTSTRAP_ADMIN_USERNAME:-}
      BOOTSTRAP_ADMIN_PASSWORD: ${BOOTSTRAP_ADMIN_PASSWORD:-}
      BOOTSTRAP_ADMIN_EMAIL: ${BOOTSTRAP_ADMIN_EMAIL:-}
      EVIDENCE_MAX_UPLOAD_MB: ${EVIDENCE_MAX_UPLOAD_MB:-25}
      OIDC_ISSUER_URL: ${OIDC_ISSUER_URL:-}
      OIDC_CLIENT_ID: ${OIDC_CLIENT_ID:-}
      OIDC_CLIENT_SECRET: ${OIDC_CLIENT_SECRET:-}
      OIDC_ENABLED: ${OIDC_ENABLED:-false}
      AI_ENABLED: ${AI_ENABLED:-false}
      AI_BASE_URL: ${AI_BASE_URL:-}
      AI_MODEL: ${AI_MODEL:-}
      AI_API_KEY: ${AI_API_KEY:-}
    volumes:
      - media:/data/media          # evidence uploads: back this up with the database
    networks: [backend, frontend]
    ports:
      - "${WEB_BIND:-127.0.0.1}:${WEB_PORT:-8000}:8000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s
    read_only: true
    tmpfs:
      - /tmp
      - /srv/.gunicorn:uid=10001,gid=10001   # gunicorn writes its control socket here
    cap_drop: [ALL]
    security_opt:
      - no-new-privileges:true
    mem_limit: 512m
    pids_limit: 200
    logging:
      driver: json-file
      options: {max-size: "10m", max-file: "3"}

networks:
  backend:
    internal: true
  frontend:

volumes:
  pgdata:
  media:
```

Back up both volumes (`pgdata` and `media`). See `docs/operations.md`.

## Sign in with OIDC

OIDC is optional. You can let people sign in through your identity provider, such as Authentik or Keycloak. Password sign-in always stays available.

OIDC never creates an account on its own. A person links OIDC in one of two ways:

- They accept an invitation and choose "Sign up with OIDC".
- They are signed in and choose "Link OIDC account" in Settings.

The app never matches people by e-mail address. A deactivated user cannot sign in.

To set it up:

1. At your provider, create an OIDC application with the authorization-code flow. Use a confidential client.
2. Register the redirect URI. It is your site address plus `/oidc/callback/`, for example `https://merit.example.com/oidc/callback/`. Settings > OIDC shows the exact value.
3. In Settings > OIDC (admin only), enter the issuer URL, client ID and client secret. The issuer URL is the address that serves `/.well-known/openid-configuration`.
   - Authentik: `https://auth.example.com/application/o/<application-slug>/`
   - Keycloak: `https://auth.example.com/realms/<realm>`
4. Select "Test discovery". Then turn on "Enable OIDC sign-in" and save.

The issuer URL must use `https://`. Only `localhost` may use `http://`. The app uses PKCE (S256) and checks state, nonce, signature, issuer, audience and expiry.

You can pre-fill the first settings with `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` and `OIDC_ENABLED` in `.env`. They apply once, when the settings row is first created. After that, Settings is the source of truth.

The client secret is stored encrypted. The key comes from `DJANGO_SECRET_KEY`. The secret is never shown again. A blank secret field keeps the current one.

If you change `DJANGO_SECRET_KEY`, the stored secret cannot be read. OIDC sign-in turns off until you enter the secret again in Settings > OIDC. Password sign-in is not affected.

## AI tutor (optional)

The AI tutor is off by default. The whole app works without it. When you turn it on, a learner can start a study session from a requirement page. The modes are Discuss, Explain, Practice, Check understanding, Prepare to demonstrate and Review my evidence.

What it will not do:

- It never marks a requirement done, never adds evidence, and never changes a requirement.
- It does not count as a counselor, a witness or a required person-to-person conversation.
- Its answers and summaries are labelled "not official". A kept session is not evidence.

To set it up:

1. Run or pick an OpenAI-compatible endpoint, such as Ollama (`http://ollama:11434/v1`), llama.cpp, vLLM or a hosted API. This project ships no model container.
2. Sign in as an admin. Open **Settings > AI tutor**.
3. Enter the endpoint URL and model name. Enter an API key if the endpoint needs one. Select **Enable the AI tutor** and save.
4. Select **Test the endpoint**.

You can pre-fill the first settings with `AI_ENABLED`, `AI_BASE_URL`, `AI_MODEL` and `AI_API_KEY` in `.env`. They apply once. After that, Settings is the source of truth. The key is encrypted with a key derived from `DJANGO_SECRET_KEY`. If you change that secret, enter the key again.

What the model sees: the requirement text, its version, its safety notes, and (in review mode) up to 10 short evidence descriptions. It never sees files, other plans or other users.

Retention: a conversation is held only while a session is open. When you end a session, you can keep the summary, keep the summary and the full conversation, or delete everything. Sessions you leave unkept are deleted after one day. Kept sessions are in your data export.

If the endpoint is down, you see a plain message and nothing else changes.

## Interface and CSS build

The interface uses Tailwind CSS 4 and DaisyUI 5. The Docker build creates the stylesheet
in a `css` stage with the Tailwind standalone CLI. The runtime image has no Node.js and
the pages load no files from outside servers.

- Source: `app/frontend/app.css`. Output: `app/static/css/app.css` (gitignored, not committed).
- The image build needs network access to GitHub to fetch the pinned CLI and DaisyUI plugin.
- The test image skips the CSS build. Tests do not need it.
- To build by hand for a local run, download the CLI and `daisyui.js` (versions in the `Dockerfile`),
  put `daisyui.js` in `app/frontend/`, then run
  `tailwindcss --input app/frontend/app.css --output app/static/css/app.css`.

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

## Invite a user

Only an admin can invite people. There is no public sign-up.

1. Open Settings, then Invitations.
2. Choose the role, the number of days the link stays valid (1 to 30), and an optional note.
3. Select Create invitation.
4. Copy the link on the next page and send it to the person. The page shows the link once. The app stores only a hash.
5. The person opens the link, picks a username and password, and is signed in.

A link works once. If it expires or you lose it, revoke it in the same list and create a new one.

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

## Scouting catalog structure

Run this once to create the structure for Cub Scouts and Scouts BSA:

```sh
docker compose exec web python manage.py seed_scouting_catalog
```

The command is safe to run again. It creates Scouting America as a named source, two draft
programs, and nothing else. It adds no requirement text and no awards. The app is unofficial
and has no recognition from Scouting America.

- Merit badges, ranks and adventures use the generic award types and requirement logic.
  Completion uses the same engine as every other program.
- Add entries with the JSON import. Each entry needs a source, a version label and a rights
  status. Entries stay unreviewed until you review them.
- Coverage is in `programs.coverage`. A catalog counts as complete only if you set
  `catalog_validated_complete` on the program, set the expected entry count, and every entry is
  published and reviewed. Otherwise the app must say "Incomplete catalog coverage".

## Tutorial

The web container adds a tutorial plan, "How to use Merit Badge", when it starts. Open it from the
home page. It is written by this project, is unofficial, and is not part of the Scouting catalog
coverage. To skip it, set `SEED_TUTORIAL=false` in `.env`. To add it by hand:

```sh
docker compose exec web python manage.py seed_tutorial
```

The command is safe to run again. It never changes a published version or your progress.
The tutorial is version 1.1. Plans started on 1.0 stay on 1.0. My Learning starts your tutorial plan
once, on your first visit. If you archive it, the app does not make another.

Use the Checklist on a plan page to mark requirements done, or the same buttons at the top of a
requirement page. The evidence rules still apply.

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

## 1911 Handbook badges

The 56 merit badges of the *Boy Scouts Handbook*, First Edition, 1911 (Project Gutenberg #29558) are in `app/programs/data/handbook_1911/`. The text is historical, not a current or official Scouting America requirement. Many badges are obsolete or unsafe today. You do not need to do anything unsafe. The book is in the US public domain because of its age. Outside the US, check your local law. This is not legal advice (see `docs/decisions/0005-1911-handbook-source.md`).

```sh
docker compose exec web python manage.py import_handbook_1911 --dry-run
docker compose exec web python manage.py import_handbook_1911
```

The command makes draft versions only and is safe to run again. It never publishes. Review each badge against Gutenberg before you publish it. `scripts/convert_1911_handbook.py` rebuilds the files from the Gutenberg HTML.

## Learning, achievements and export

Sign in, open a published version in the catalog, and choose **Start plan**. **My Learning** lists
your plans. Each requirement page shows the official text, notes, evidence and status. Reading or
claiming prior knowledge never completes a requirement. When every mandatory requirement is
satisfied, the plan page offers **Record personal completion**. That creates an achievement record
and a printable certificate (use the browser's print dialog). Certificates say they are personal and
unofficial.

Evidence files are stored privately on this server, not at public URLs. **Settings** lets you set a
display name, download a JSON export, and download a zip of your evidence files. The format is in
`docs/schemas/personal-export.md`. Account deletion is not built yet.

## Layout

`app/programs`, `app/requirements`, `app/learning`, `app/evidence`, `app/achievements` (models, services, views, importer), `app/config` Django project (settings, urls, `core` health/home views and the
`bootstrap_admin` command), `app/templates`, `tests/`, `docs/` (operations and
`decisions/` ADRs), `scripts/entrypoint.sh`, `compose.yaml`, `Dockerfile`.
