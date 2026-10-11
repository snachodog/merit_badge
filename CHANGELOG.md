# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.0] - 2026-10-10


### Added
- Phase 0 foundation: Django 5.2 project (`app/config`), PostgreSQL via environment
  variables, `/healthz` database check, login-required home page, login/logout,
  no public registration, `bootstrap_admin` management command.
- Docker (non-root, pinned base) and Compose deployment with healthchecks, named
  volumes for database and media, PostgreSQL not published to the host.
- `.env.example`, README, `docs/operations.md` (backup/restore), ADRs 0001-0003.
- pytest-django tests for health check, auth redirect, and absence of registration routes.
- Phase 1 part A (data model): new `programs` app (ProgramOwner, Program, Award, AwardVersion)
  and `requirements` app (RequirementNode, RequirementActionTag, SourceRecord), with migrations.
- Version workflow draft -> review -> published -> archived. Published and archived versions,
  their nodes, and their action tags cannot be changed or deleted at model level.
  `requirements.services.create_revision` copies a published version into a new linked draft.
- Pure tree rules (`requirements/tree_rules.py`) for single, all, any, choose_n, sequence,
  and conditional logic. Publishing checks the tree and the source and rights rules.
- Django Admin for all models with an inline requirement editor; published versions are read-only.
- Tests for tree rules, immutability, revisions, publish rules, and admin permissions.
- Phase 1 part B: catalog browse and search (names, descriptions, requirement text), with version
  status and content-review labels.
- Nested requirement display with display numbers, completion-logic labels, action tags, and
  "Official text" versus not-official labels. Login required.
- Manual authoring pages for custom programs, awards, draft versions and nested requirements
  (add child, edit, reorder, delete), with submit, publish, return, archive and revise.
- JSON import: schema `docs/schemas/program-import.schema.json`, example file, dry-run report with
  error paths, import keys for repeat imports, drafts only, `import_program` command, and an upload page.
- `ImportRecord` model and migration `requirements.0002`.
- `user_authored` source status for content you write yourself, with its own banner text.
