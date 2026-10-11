# 0001 - Application stack

Status: Accepted

## Context
PLAN.md section 5 recommends a simple, self-hosted, server-rendered stack deployed
with Docker Compose for a single-user-first personal deployment. The repository
had no prior code.

## Decision
- Django 5.2 (LTS) as a single modular monolith; Django templates, auth and admin.
- PostgreSQL 16 via psycopg 3 (`psycopg[binary]`), configured by environment variables.
- gunicorn as the WSGI server; WhiteNoise serves static files (no extra proxy container).
- Docker Compose with two services (`web`, `db`); migrations run in the web entrypoint;
  startup ordering via `depends_on: service_healthy`.
- Dependencies pinned in `requirements.txt` / `requirements-dev.txt`; base images pinned by tag.
- No Redis, Celery, vector DB, analytics, or SaaS dependencies.
- Domain apps (programs, requirements, ...) are created only when their phase begins.
  Phase 0 code lives in `config.core`.

## Consequences
Minimal operational surface and easy backup (one database, one media volume).
Adding background work or search infrastructure later requires a new ADR.
Tests need PostgreSQL (provided through the compose `test` profile).
Image tags are not digest-pinned; digest pinning is a possible hardening step.
