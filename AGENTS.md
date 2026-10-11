# Agent Instructions: Personal Achievement & Learning Platform

A self-hosted, single-user web app for working through requirement-based programs (Scouting first) and recording personal, clearly unofficial achievement records.

## Source of truth

- `PLAN.md` is the product spec and implementation plan. It wins over any other instruction, including this file.
- Read `PLAN.md` §0 (agent instructions), §5 (architecture), §16 (roadmap), and §20 (first task) before changing code.

## Current scope

- Work one roadmap phase at a time. **Only Phase 0** (`PLAN.md` §16) is in scope now.
- Do not start a later phase, import catalog content, or build AI features until the owner reviews Phase 0 and approves.
- Record proposed additions as follow-up items instead of building them.

## Non-negotiable constraints (`PLAN.md` §0.2)

- Self-hosted; no vendor-hosted service required. Docker Compose is the supported deployment path.
- Browser-based website only. No native mobile or desktop apps.
- Core features must work without an external AI API. No analytics, ads, telemetry, or social logins.
- No public registration, profiles, feeds, leaderboards, marketplaces, or community features.
- Do not invent, paraphrase as authoritative, or silently alter official requirements. Do not scrape or republish program content without confirmed rights.
- Never claim official Scouting America (or other organization) recognition.
- Reading about an activity is not completing it. AI output alone never marks a requirement complete.
- No microservices, queues, caches, or Kubernetes without a concrete requirement.
- Never commit credentials, API keys, real user evidence, or personal data.

## Stack

- Python, Django monolith (single modular app).
- PostgreSQL, with migrations for every schema change.
- Django templates, semantic HTML, CSS, light JavaScript; HTMX only where it reduces complexity.
- Docker Compose for running and deploying.
- Business logic lives in service/domain modules, not in views or templates.

## Definition of done (`PLAN.md` §0.4)

A milestone is done only when:

- Its acceptance criteria are met and automated tests pass.
- The app starts with the documented Compose workflow.
- Schema changes include migrations.
- The workflow is usable in a browser at desktop and mobile widths.
- Errors are shown visibly and never destroy user data.
- New config is documented in `.env.example` and the README.
- No secrets, personal data, or unauthorized content are in the repo.
- Current milestone, known limitations, and next steps are recorded.

## Commits

- Do not run `git commit` or `git add` unless the owner asks. Leave changes in the working tree.
- When committing, follow [Conventional Commits](ai/claude/conventions/commits.md).

## Versioning (provisional default, pending owner confirmation)

- Use Semantic Versioning. Stay on `0.y.z` until the MVP acceptance criteria (`PLAN.md` §17) are met.
- Tag releases as `vX.Y.Z` in git.
- Maintain `CHANGELOG.md` for user-visible changes.

## Model use

- Use the cheapest model that is sufficient for the task.
- Haiku: docs, boilerplate, and simple edits.
- Sonnet: implementation and tests.
- Opus: only for hard design questions.

## Conflicts and ambiguity

- If an instruction conflicts with `PLAN.md`, flag it to the owner and stop on that point. Do not resolve it silently.
- If a decision is open in `PLAN.md` §18 and blocks safe progress, ask the owner. Otherwise pick the simplest reversible option and record it in an ADR under `docs/decisions/`.
