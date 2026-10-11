# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.3.0] - 2026-10-11

### Added
- Phase 2 part B (learner screens): My Learning, start a plan from a published version (with a
  requirement summary first), plan overview with derived status counts and outstanding required items,
  and a requirement page with the six sections of `PLAN.md` 4.2. Forms cover prior knowledge, notes,
  status changes, conditional answers, self-attestation, evidence (note, text, link, file, time log),
  evidence deletion, human observation, and plan pause, resume, abandon, archive and completion.
- New `achievements` app: AchievementRecord, created only when a plan is personally completed.
  Printable HTML certificate with a versioned disclaimer (`achievements/disclaimer.py`) and an
  Achievements list. No official graphics.
- Settings page with display name, JSON data export, and a separate zip of evidence files.
  Format: `docs/schemas/personal-export.md`.
- Navigation: My Learning, Achievements, Settings.
- Phase 2 part A (no learner screens yet): new `learning` app (LearningPlan, RequirementProgress,
  PlanStatusLog) and `evidence` app (EvidenceRecord), with migrations.
- Plans start only from a published version and stay pinned to it. Creating a plan creates a
  progress row for every requirement. Plan changes (planned, active, paused, personally completed,
  abandoned, archived) are logged.
- Pure completion engine (`learning/completion.py`) for single, all, any, choose_n, sequence and
  conditional logic. It returns complete, incomplete, unresolved or not applicable per node, plus the
  outstanding items. Counts come from the engine; there is no editable percentage.
- Prior knowledge and prior work notes never complete a requirement. `not_applicable_by_explicit_rule`
  is accepted only when a conditional rule makes the branch not apply.
- Action-tag rule: tags such as interview, teach and demonstrate need suitable evidence or an explicit
  learner attestation before completion. The mapping is in `learning/constants.py`.
- `evidence_expectations` on requirements (migration `requirements.0003`), stored by the JSON importer.
- Evidence uploads: extension, size, content-type and signature checks, generated file names, private
  storage under `DJANGO_MEDIA_ROOT/evidence`, owner-checked download view, deletion report and delete.
  `human_observed` needs a reviewer label and is set only by a service function.
- `EVIDENCE_MAX_UPLOAD_MB` setting (default 25), documented in `.env.example`.

### Follow-ups
- Delete-my-data (account-level deletion, `PLAN.md` 13.3) is not built. Single evidence deletion works.
- Interpretation and learning-resource content on the requirement page are placeholders (later phases).

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
