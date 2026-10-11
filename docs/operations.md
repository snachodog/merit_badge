# Operations: backup and restore

A database backup alone is **not sufficient**: uploaded evidence lives in the
`media` volume and is referenced by the database. Back up both, taken as close
together in time as practical, and keep copies off the host. Backups contain
personal data; protect and encrypt them accordingly. Never commit them.

Commands assume you run them in the repository directory with `.env` present.
Compose project name is `meritbadge`; volumes are `meritbadge_pgdata` and `meritbadge_media`.

## Backup

```sh
STAMP=$(date +%Y%m%d-%H%M%S); mkdir -p backups/$STAMP

# 1. PostgreSQL (logical dump, custom format)
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > backups/$STAMP/db.dump

# 2. Media/evidence volume
docker run --rm -v meritbadge_media:/data:ro -v "$PWD/backups/$STAMP":/out \
  debian:bookworm-slim tar -C /data -czf /out/media.tar.gz .

# 3. Configuration (contains secrets - store securely, not in git)
cp .env backups/$STAMP/env.backup
```

`backups/` should be outside version control (add it to your local ignore rules)
or point the output at another disk. Schedule with cron/systemd and prune old copies.

## Restore (into a fresh or non-production project first)

Restoring overwrites existing data. Confirm the target before running anything.
Periodically rehearse a restore in a separate Compose project:

```sh
# Separate project name => separate volumes, no risk to production data.
# Use a different WEB_PORT in the copy of .env to avoid port conflicts.
export COMPOSE_PROJECT_NAME=meritbadge_restoretest
```

Steps (for the project selected by `COMPOSE_PROJECT_NAME`):

```sh
B=backups/<STAMP>
docker compose up -d db                       # start only the database
docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner' < $B/db.dump

docker volume create ${COMPOSE_PROJECT_NAME}_media
docker run --rm -v ${COMPOSE_PROJECT_NAME}_media:/data -v "$PWD/$B":/in \
  debian:bookworm-slim sh -c 'cd /data && tar -xzf /in/media.tar.gz && chown -R 10001:10001 /data'

docker compose up -d                          # migrations run on start
curl http://127.0.0.1:${WEB_PORT:-8000}/healthz
```

Restoring over **production** additionally requires: `docker compose stop web`
first, a fresh backup of the current state, and a deliberate decision that the
`dropdb` step is intended. This repository ships no automated destructive restore script.

## Health and logs

`/healthz` returns 200 `{"status":"ok"}` when the app can query the database
(503 otherwise). Compose healthchecks use it. `docker compose logs -f web db`.

## Data export / deletion

A portable export format and account-level deletion procedure arrive with the
features that create personal data (PLAN.md section 13.3). Until then, the backup
above is the complete export.
