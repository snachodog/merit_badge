# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Phase 0 foundation: Django 5.2 project (`app/config`), PostgreSQL via environment
  variables, `/healthz` database check, login-required home page, login/logout,
  no public registration, `bootstrap_admin` management command.
- Docker (non-root, pinned base) and Compose deployment with healthchecks, named
  volumes for database and media, PostgreSQL not published to the host.
- `.env.example`, README, `docs/operations.md` (backup/restore), ADRs 0001-0003.
- pytest-django tests for health check, auth redirect, and absence of registration routes.
