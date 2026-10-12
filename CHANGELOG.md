# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]
### Added
- Sign in with OIDC (Authentik, Keycloak and others). Admins set it up in Settings > OIDC. It uses PKCE and checks the ID token. It never creates an account by itself: people link it through an invitation or in Settings. Password sign-in always works. New `OIDC_*` variables can pre-fill the settings.
- Invitations: an admin creates a single-use link in Settings, picks the role and the expiry (1 to 30 days, default 7), and sees the link once. The link is stored only as a hash. The person opens it, picks a username and password, and is signed in. Admins can revoke links. Invitation events are audited.
- Roles: admin and user. The first user, and every staff or superuser, is an admin. Admins manage users in Settings: change role, deactivate, reactivate, reset a password. The last active admin cannot be demoted, deactivated or deleted. Account changes are audited.
- Every signed-in user can create, import and edit their own programs. Programs have a visibility: private, shared with chosen users, or shared with all. Only admins change it. Others get a 404 for programs they cannot see. Existing custom programs go to the first admin as private. Seeded programs are visible to all.
- My Learning starts the "How to use Merit Badge" plan for you, once. A plan you archive or abandon is not recreated.
- The plan page has a checklist with Mark done and Undo. The requirement page has the same buttons. The usual evidence rules still apply and a refusal explains why.
- My Learning shows "X of Y done" for each plan.
- Tutorial version 1.1. Existing plans stay on 1.0.

### Changed
- Learner pages no longer show "Not official text" or action-tag badges. "Official text" shows only for official text. Tags show in the editor as "Action tag".

## [0.5.1] - 2026-10-12
### Fixed
- Page sections no longer overlap. The `stack` helper class clashed with the DaisyUI `stack` component, so requirements were hidden behind the status card on version, plan, settings and import pages. It is now `vstack`.

### Added
- The award page lists the requirements of its current version.
- You can delete a draft or review version. Published and archived versions cannot be deleted.

### Changed
- Removed the "written by you", "records personal learning" and "content is unverified" callouts. The unverified note may return in another form.
- The coverage alert is now a small "Coverage incomplete" badge that expands for details.

## [0.5.0] - 2026-10-11
### Added
- `import_handbook_1911` command and `scripts/convert_1911_handbook.py`: all 56 merit badges with requirements in the 1911 Boy Scouts Handbook (Scholarship has none) as draft versions (public domain in the US; historical text, not official). Never published by the command. Not counted in Scouting catalog coverage. See `docs/decisions/0005-1911-handbook-source.md`.
- `seed_tutorial` command and the "How to use Merit Badge" tutorial plan. The container runs it at start unless `SEED_TUTORIAL=false`. The home page links to it. It is not counted in Scouting catalog coverage.

## [0.4.0] - 2026-10-11
### Changed
- New interface built with Tailwind CSS 4 and DaisyUI 5 (light and dark themes, collapsing navbar). CSS is built in a Docker `css` stage with the Tailwind standalone CLI. No CDN, no Node.js at runtime. See `docs/decisions/0004-daisyui-tailwind.md`.

### Added
- Catalog list and program pages show coverage: validated and unvalidated counts, unknown totals and reasons. Award pages show source URLs. Nothing is called complete unless validated.
- `seed_scouting_catalog` command: Scouting America as a named source, plus draft Cub Scouts and Scouts BSA programs. No requirement text.
- Program fields for catalog source URL, expected entry count and a validated-complete flag (migration `0003`).
- `programs.coverage`: per-program counts of validated and unvalidated entries. A catalog is never called complete unless you validate it.

## [0.3.2] - 2026-10-11
### Changed
- The web container now runs `bootstrap_admin` at start when `BOOTSTRAP_ADMIN_USERNAME` and `BOOTSTRAP_ADMIN_PASSWORD` are set. Before, `.env` values alone created no user (issue #1).

### Fixed
- `bootstrap_admin` now says when an existing user keeps its password, and has `--reset-password` to set a new one (issue #1).

## [0.3.1] - 2026-10-11

### Added
- `sample.docker-compose.yaml` and `sample.env` for running the published image.
- README section "Run from the published image" with a minimal and a robust compose file.
- GitHub Actions release job: a `v*` tag builds the image, tags it `latest`, and creates a
  GitHub release (pre-release while the version is 0.x).

### Fixed
- The Docker build workflow now builds the root `Dockerfile` and the `runtime` stage.
- ntfy notifications are optional; the build no longer needs those secrets.

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
