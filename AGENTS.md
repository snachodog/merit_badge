# Agent Instructions: Personal Achievement & Learning Platform

A self-hosted, single-user web app for working through requirement-based programs (Scouting first) and recording personal, clearly unofficial achievement records.

## Source of truth

- `PLAN.md` is the product spec and implementation plan. It wins over any other instruction, including this file.
- Read `PLAN.md` §0 (agent instructions), §5 (architecture), §16 (roadmap), and §20 (first task) before changing code.

## Current scope

- Work one roadmap phase at a time. **Only Phase 3a** (`PLAN.md` §16, the tutorial learning plan for 0.5.0) is in scope now. Phases 0 to 3 are done.
- Do not start a later phase or build AI features until the owner reviews Phase 3a and approves.
- Record proposed additions as follow-up items instead of building them.

## Non-negotiable constraints (`PLAN.md` §0.2)

- Self-hosted; no vendor-hosted service required. Docker Compose is the supported deployment path.
- Browser-based website only. No native mobile or desktop apps.
- Core features must work without an external AI API. No analytics, ads, telemetry, or social logins.
- No public registration, profiles, feeds, leaderboards, marketplaces, or community features.
- Do not invent, paraphrase as authoritative, or silently alter official requirements.
- `source_reqs/` is a local-only, gitignored scratch folder of requirement text for internal testing. Never commit it, bake it into an image, or ship it in seed data.
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

- Do not run `git commit` or `git add` unless the owner asks. Leave changes in the working tree. The owner has asked the lead session to commit finished work.
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

## Plain language (ISO 24495-1)
All text written for people follows ISO 24495-1 (see PLAN.md §2.6): docs, UI text, error messages, ADRs, commit messages, and every message to the project owner. Working rules come from the community skill at https://github.com/GaZmagik/iso-24495 (MIT, `skills/iso-24495-1/SKILL.md`). Its numbers are its own proxies, not the standard's text, so following them is not a claim of ISO conformance.

- **Lead with the answer.** No preamble or filler.
- **Short sentences.** Aim for 15 to 20 words; never over 30. One idea each.
- **Short paragraphs.** 3 to 5 sentences, one topic, main point first.
- **Active voice, everyday words.** One term per concept. Say "you". State links with *because*, *if*, *before*, *after*.
- **Easy to scan.** Single-topic headings; bullets for three or more items. Do not rely on bold or colour alone for meaning.
- **Give the next action.** Exact commands, paths, and parameters.
- **Exemptions.** Code, commands, logs, diffs, and quoted files stay unaltered. Official requirement text is reproduced exactly. Technical accuracy outranks style.

## No bylines
Do not add bylines or attribution to anything. This covers `Co-Authored-By` and `Claude-Session` trailers in commits, and "Generated with" lines or session links in pull request descriptions. Commit messages contain only the Conventional Commits message.
