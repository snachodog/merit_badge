#!/bin/sh
# Apply migrations, create the first user if asked, then exec the container command.
# Database readiness is ensured by compose (depends_on: service_healthy);
# migrate also retries briefly to tolerate non-compose use.
set -eu

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  tries=0
  until python manage.py migrate --noinput; do
    tries=$((tries + 1))
    if [ "$tries" -ge 10 ]; then
      echo "migrate failed after $tries attempts" >&2
      exit 1
    fi
    echo "migrate failed; retrying in 3s ($tries/10)" >&2
    sleep 3
  done
fi

# Create the first user if both variables are set. Does nothing if the user exists.
if [ -n "${BOOTSTRAP_ADMIN_USERNAME:-}" ] && [ -n "${BOOTSTRAP_ADMIN_PASSWORD:-}" ] \
  && [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  python manage.py bootstrap_admin || echo "bootstrap_admin failed; continuing" >&2
fi

exec "$@"
