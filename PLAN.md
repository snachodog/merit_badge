# Personal Achievement & Learning Platform
## Product Specification and Implementation Plan

**Document status:** Product and engineering specification draft 1.0  
**Working name:** Personal Achievement & Learning Platform (PALP). “Merit Badge Counselor” remains a possible project name, but must not be assumed to imply official Scouting affiliation.  
**Primary deployment:** Self-hosted Docker Compose on a private server  
**Primary interface:** Responsive website accessed in a web browser  
**Primary user:** The owner/operator, initially a single adult learner  
**Primary initial content:** Scouting America youth-program requirements, especially Cub Scouts, Scouts BSA rank requirements, and merit badges  
**Long-term direction:** Program-agnostic requirement-based learning, practice, evidence, and personal achievement records

---

## 0. Instructions for AI Coding Agents

This document is the project's product specification and implementation plan. Treat it as the source of truth unless the project owner explicitly changes it.

### 0.1 Work incrementally

Do not attempt to implement every phase in one pass. Implement one milestone at a time, keep the application runnable, and leave the repository in a tested state after each milestone.

Before making changes:

1. Inspect the existing repository and report its current structure, framework, and state.
2. Read this specification fully.
3. Identify the current milestone and its acceptance criteria.
4. Propose a short implementation plan for that milestone.
5. Preserve existing working behavior unless a change is explicitly required.

Do not generate an entire application blindly if a repository already exists. If no repository exists, use the default architecture in Section 5 unless the project owner approves a different stack.

### 0.2 Non-negotiable constraints

- The application is self-hosted. It must not require a vendor-hosted application service to function.
- The primary client is a browser-based website. Do not build native mobile or desktop apps.
- Docker Compose is the supported deployment path.
- Core features must work without an external AI API.
- Do not require analytics, advertising, telemetry, social logins, or other SaaS services.
- Do not implement public registration, public profiles, social feeds, leaderboards, marketplaces, or community features unless explicitly requested later.
- Do not invent, paraphrase as authoritative, or silently alter official requirements.
- Do not scrape or republish program content in the repository, in container images, in seed data, or in any shipped or shared build, unless the source and applicable permissions allow it. Exception: for local, internal testing only, the owner may place requirement text in the gitignored `source_reqs/` folder (see Section 11.1).
- Do not claim that the app confers official Scouting America or another organization's awards.
- Do not equate reading about a practical activity with completing it.
- Do not mark a requirement complete solely because an AI agent says it is complete.
- Do not add microservices, queues, caches, Kubernetes, or other infrastructure without a concrete requirement.
- Never commit credentials, API keys, real user evidence, or personal data.

### 0.3 Engineering discipline

- Keep business logic in explicit service/domain layers rather than embedding it entirely in views or templates.
- Use database migrations for schema changes.
- Add automated tests for requirement logic, version behavior, progress calculations, permissions, imports, and critical workflows.
- Prefer simple, readable code over premature abstraction.
- Document consequential architecture decisions in `docs/decisions/` using short Architecture Decision Records (ADRs).
- Maintain `README.md`, `.env.example`, deployment instructions, upgrade instructions, and backup/restore instructions.
- Validate all input. Treat imported files, uploaded evidence, external resources, and model output as untrusted input.
- Where this specification leaves a decision open, choose the simplest reversible option and document the decision. Ask the project owner only when the ambiguity blocks a safe or coherent implementation.
- Do not silently change scope. Record proposed additions as follow-up items.

### 0.4 Definition of done for a milestone

A milestone is complete only when:

- Its acceptance criteria are satisfied.
- Automated tests pass.
- The app starts using the documented Docker Compose workflow.
- Schema changes have migrations.
- The user-facing workflow is usable in a browser at desktop and mobile widths.
- Errors are handled visibly and do not destroy user data.
- Any new configuration is documented in `.env.example` and the README.
- No secrets, personal data, or unauthorized copyrighted content are included in the repository.
- The current milestone, known limitations, and next steps are recorded in project documentation.

---

# 1. Product Vision

## 1.1 One-sentence definition

A private, self-hosted, browser-based platform that turns learning goals into structured requirements, helps a person learn and practice, records honest evidence of what they did, and preserves personal achievements over time.

## 1.2 Personal objective

The owner's first practical use is to work through requirements and skills that were missed during childhood Scouting, including Cub Scout requirements, Scouts BSA rank advancement requirements, and merit badges. Over time, the owner may explore historical versions of those requirements and other programs.

The software should serve this personal objective directly. It is not necessary to optimize the first release for an imagined public market or community.

## 1.3 General design objective

The learning engine must be program-agnostic. Scouting America is the initial flagship content family, not a hard-coded assumption that every award behaves like a merit badge.

The platform should eventually accommodate:

- Official or authorized requirements from a recognized organization.
- Older or historical versions of official requirements.
- Programs from other youth Scouting organizations.
- Private, self-authored learning plans.
- Custom achievements and personal certificates.
- Other structured learning programs with explicit activities and completion criteria.

Examples of possible later program sources include Girl Scouts of the USA, Royal Rangers, Trail Life USA, international Scouting organizations, and other US programs such as Explorers, Venturing, and Sea Scouts. These are future candidates, not required MVP catalogs.

Wood Badge and other non-youth/adult Scouting programs are out of scope unless the project owner explicitly broadens the scope in a future decision.

## 1.4 Product promise

The platform helps a learner answer five questions:

1. What am I trying to learn or accomplish?
2. What exactly is required?
3. How can I learn and practice the necessary knowledge or skill?
4. What did I actually do, and what evidence supports that claim?
5. What have I completed, and under which version or criteria?

The app records personal learning and achievement. It does not confer official awards, certifications, licenses, or rank advancement unless a future authorized integration and formal authority explicitly establish that capability.

---

# 2. Guiding Principles

## 2.1 Faithfulness to requirements

Requirements define the outcome and the actions expected from the learner. The platform may clarify, teach, organize, and help assess them, but it must not silently lower their standards.

Examples:

- **Discuss** means a meaningful dialogue about the requested topic. A static article or multiple-choice quiz alone is not an equivalent activity.
- **Demonstrate** means the learner performs the specified skill. Watching a video is preparation, not demonstration.
- **Explain** means the learner articulates an explanation in their own words. Copying generated text is not adequate proof of understanding by itself.
- **Read** means completing the requested reading. A summary can supplement but must not silently replace it.
- **Build, make, prepare, plan, or conduct** means carrying out the requested activity or producing the specified work.
- **Interview** means conducting the required interview with an appropriate person. An AI chat cannot substitute for an actual human interview.
- **Teach** means teaching another person where that is what the requirement says.
- **Participate, visit, observe, or keep a log** must be represented as the relevant real-world activity, not an interchangeable lesson.

The data model must represent compound requirements, parent/child relationships, alternatives, required counts, time windows, prerequisites, and repeat activities explicitly enough to calculate progress correctly.

## 2.2 The Scout Oath and Scout Law

For Scouting-related content and workflows, the application should respect the intent of the Scout Oath and Scout Law. At platform level, it should act consistently with honesty, helpfulness, courtesy, kindness, trustworthiness, safety, and respect for differing backgrounds and beliefs.

The app must not use a values framework to justify coercion, harassment, discriminatory treatment, political advocacy, or unrelated moral judgments.

Custom programs can specify their own values or instructional principles. Do not imply that every custom program is an official Scouting program or governed by Scouting America.

## 2.3 EDGE as an instructional pattern

Use EDGE where it materially improves learning:

1. **Explain:** Define the topic, why it matters, terminology, prerequisites, and safety considerations.
2. **Demonstrate:** Show a worked example or a skill being performed.
3. **Guide:** Support practice, questions, troubleshooting, and incremental feedback.
4. **Enable:** Ask the learner to perform or explain the skill independently.

EDGE is an instructional framework, not an alternative to a requirement. It must not be used to waive a required person-to-person conversation, practical task, time period, project, interview, or other stated condition.

Not every requirement needs four separate screens. Apply EDGE proportionately, based on the type of requirement and learner's experience.

## 2.4 Achievement should represent learning

The platform may use achievement icons, completion summaries, certificates, and progress indicators, but must not reward clicking through lessons or accumulating points as substitutes for learning.

Do not add streaks, points, leaderboards, loot-box mechanics, or engagement loops by default. Motivation should primarily come from meaningful goals, visible progress, useful feedback, and a reliable record of accomplishment.

## 2.5 Respect adult learners

Use direct, respectful language. Avoid infantilizing visual design, unnecessary gamification, compulsory social interaction, and assumptions that all learners are beginners.

Users should be able to move quickly through material they already understand while still addressing the actual requirements.

## 2.6 Honest evidence

The app must distinguish between:

- A user saying they completed something.
- Evidence supplied by the user.
- A human witness or reviewer recording an observation.
- AI-generated formative feedback.
- A formally authorized external approval, if such a concept is ever supported.

These are not equivalent states and must never be collapsed into a generic "verified" label.

---

# 3. Scope

## 3.1 MVP: required capabilities

The MVP should include:

1. Self-hosted browser-based application with authentication.
2. Generic programs, awards, versions, and nested requirements data model.
3. A way to create custom programs and requirements manually.
4. A structured import path for requirements from JSON, plus a documented schema. CSV may be added for simple flat lists but must not be the canonical format for nested requirements.
5. Program catalog and search.
6. Learning plans built from an award/version or a custom program.
7. Per-requirement and per-subrequirement progress tracking.
8. Requirement types and action tags that guide appropriate completion workflows.
9. Notes and evidence records, including file uploads where configured.
10. Personal completion summaries and clearly unofficial certificates.
11. Versioning from the beginning, including the ability to preserve a plan's chosen requirement version.
12. Basic administration for editing content, sources, versions, and resources.
13. Backup and restore guidance.
14. Responsive, accessible browser UI.
15. Core functionality without an AI provider configured.

The MVP data model and interfaces should accommodate Cub Scout rank/adventure requirements, Scouts BSA rank requirements, and merit badges. Actual official catalog coverage may be staged according to source availability, permissions, and validation capacity. The app must clearly show which catalog content is populated and reviewed rather than implying completeness when it is not.

## 3.2 MVP: optional or second milestone

These features are valuable but must not block the first functional learning workflow:

- AI tutor integration.
- Source-grounded discussion agents.
- Automated or assisted resource recommendations.
- Curated YouTube video records.
- Evidence review assistance by AI.
- Rich certificate theming.
- Calendar integrations and reminders.

Keep integration points clean so these can be added without replacing the core data model.

## 3.3 Out of scope unless explicitly approved

- Official Scouting America advancement, counselor approvals, registration, or award issuance.
- Unapproved write access to Scoutbook or other official records.
- Native iOS, Android, Windows, or macOS application.
- Public user registration or a public user directory.
- Social networking, feeds, chat between users, groups, or leaderboards.
- Instructor marketplace, payment processing, or subscriptions.
- Multi-tenant SaaS operating model.
- Public custom-program marketplace in the MVP.
- Mandatory third-party cloud services.
- Automatic acceptance of an AI response as proof of actual practical performance.
- Rehosting third-party videos without authorization.
- Adult Scouting training programs, including Wood Badge, unless separately approved.

## 3.4 Roadmap candidates

- Historical Cub Scout, Scouts BSA, rank, and merit badge requirement catalogs.
- Compare two requirement versions and show changes.
- Determine whether work completed under a historical requirement version satisfies a newer version's requirements, and carry that progress forward with explicit learner confirmation (never automatically). Out of scope until designed; revisit with Phase 6.
- Broader and more complete official Scouting America catalog coverage.
- Other US youth program catalogs.
- International programs and localized requirement text.
- Other organizations' youth awards and requirements.
- Religious emblems and other specialized awards where appropriate and authorized.
- Shared user-created programs and certificate templates.
- Advanced evidence portfolios and optional human review.
- Video discovery using permitted APIs.

---

# 4. Product Workflows

## 4.1 Start a learning plan

1. User searches or browses a program and award, or creates a custom achievement.
2. User chooses a specific requirement version when multiple versions are available.
3. The application displays purpose, requirements, prerequisites, expected activities, known safety considerations, and available resources.
4. User starts a plan.
5. User may record prior knowledge and prior work against individual requirements.
6. The application presents remaining work and suggested next steps.

Prior experience must never automatically waive an explicit requirement. The UI must distinguish "I already know this" from "I performed this required activity and recorded it."

## 4.2 Work on a requirement

A requirement page should separate these sections:

1. **Requirement text:** Authoritative wording from the selected source/version, or user-authored text for a custom program.
2. **Interpretation:** Optional plain-language explanation labeled as explanatory, not authoritative.
3. **Learn:** Instruction and references.
4. **Demonstrate or complete:** The action actually called for by the requirement.
5. **Evidence and notes:** A place to record what the user did.
6. **Progress:** Current state and outstanding subrequirements.

The most relevant action should be obvious. Avoid forcing a multi-step wizard on every simple requirement.

## 4.3 Complete a learning plan

1. The system calculates completion based on requirement logic, not a user-editable percentage.
2. The user reviews outstanding and completed requirements.
3. The app produces a personal achievement summary with source/version details.
4. Where appropriate, the user may generate a personal certificate that is clearly not an official award.
5. The record stays linked to the exact requirement version used, even if a new version is later published.

## 4.4 Custom achievement creation

The user should be able to define:

- Name and description.
- Purpose or learning outcomes.
- Requirements and nested subrequirements.
- Required order or dependencies, if any.
- Alternatives or choose-N groups, if any.
- Required quantities, intervals, or durations.
- Suggested learning resources.
- Evidence expectations.
- Optional external review or witness rules.
- Completion statement for a personal certificate.

Creation should be possible without AI. AI may be used to improve clarity, find missing conditions, suggest evidence types, or create draft learning materials, but all generated material must remain editable and clearly draft until accepted by the user.

---

# 5. Recommended Technical Architecture

## 5.1 Default stack

Unless repository inspection or the project owner dictates otherwise, use a simple, maintainable, server-oriented stack:

- **Backend:** Python with Django.
- **Database:** PostgreSQL.
- **Frontend:** Django templates, semantic HTML, CSS, and lightweight JavaScript. HTMX may be used for targeted dynamic interactions where it reduces complexity.
- **Admin interface:** Django Admin for trusted content and configuration management, supplemented with custom learner-facing pages.
- **Deployment:** Docker Compose.
- **Evidence storage:** Local persistent Docker volume initially, behind an application storage abstraction so an S3-compatible service can be considered later.
- **AI:** Optional provider adapter layer. Do not require a model provider for core use.

Django is recommended because it provides mature authentication, ORM, migrations, administration, forms, permissions, and a well-understood deployment model. A single, modular Django application is preferable to multiple application services for a personal deployment.

Do not add Redis, Celery, a vector database, or a separate AI microservice until a concrete feature requires one. Begin with PostgreSQL full-text search or ordinary indexed queries. Add retrieval/vector infrastructure only after the catalog and source corpus justify it.

If choosing another stack, record the reasons in an ADR and retain all product requirements in this specification.

## 5.2 Logical modules

Keep code organized by domain boundaries. Suggested Django apps or modules:

- `accounts`: user authentication and preferences.
- `programs`: organizations, programs, awards, and award versions.
- `requirements`: requirement hierarchy, logic, versioning, import/export.
- `learning`: learning plans and per-requirement progress.
- `evidence`: notes, attachments, witnesses, and review records.
- `resources`: sources, tutorials, links, and video records.
- `tutoring`: optional AI provider adapters, prompts, and tutoring sessions.
- `achievements`: personal completion summaries and certificates.
- `audit`: material changes and administrative history.

This is a logical organization, not a requirement to create a separate deployable container for each module.

## 5.3 Runtime behavior

- The website is served by the host through a browser.
- Application and database containers run under Docker Compose.
- App data persists outside ephemeral containers using named or bind-mounted volumes.
- The application must not assume its container filesystem is durable.
- Uploaded files must be validated and stored outside the public static directory.
- The default configuration must not expose PostgreSQL directly to the LAN or internet.
- The web service should listen on a configurable port and be suitable for use behind an existing reverse proxy.
- TLS termination may occur at the user's reverse proxy. Document the required proxy headers and secure-cookie configuration.
- Provide health checks and a predictable startup process, including database readiness.

## 5.4 Docker Compose expectations

The repository should include:

- `compose.yaml` or `docker-compose.yml`.
- `Dockerfile`.
- `.env.example` with non-secret defaults and comments.
- A named persistent volume for PostgreSQL.
- A persistent location for user-uploaded evidence and generated certificates.
- Health checks and restart policies appropriate to the service.
- A documented initialization/bootstrap process.
- A documented update and migration process.
- A backup and restore procedure.

Do not commit a real `.env` file. Do not bake secrets into the image. Pin production image dependencies deliberately rather than relying on unreviewed `latest` tags.

The default Compose deployment should not start a local LLM stack automatically. Local inference can be configured to use an existing local model service, or added as an explicit optional Compose profile later.

## 5.5 Security baseline

- Require authentication for personal records and administrative operations.
- Do not enable public self-registration in the initial deployment.
- Document first-user creation or admin bootstrap clearly.
- Use Django's CSRF protections and secure session defaults.
- Apply secure cookie settings when deployed behind HTTPS.
- Validate content type, extension, size, and storage path for uploaded files.
- Prevent path traversal and direct public access to private evidence files.
- Add authorization tests for private records.
- Keep dependency versions reviewed and updateable.
- Avoid telemetry and third-party tracking by default.
- Provide a clear data-export and data-deletion path, even in single-user mode.

---

# 6. Core Domain Model

The data model must separate authoritative program definitions from the learner's personal activity. Requirements should be stable records associated with immutable published versions. Personal progress records must never be stored directly on the shared requirement definition.

## 6.1 ProgramOwner

Represents the organization, individual, or source that defines a program.

Suggested fields:

- `id`
- `name`
- `slug`
- `owner_type`: organization, individual, or other defined category
- `website_url`, optional
- `description`, optional
- `country_or_region`, optional
- `default_language`
- `created_at`, `updated_at`

Examples include Scouting America or the owner of a custom private program. Do not hard-code a single organization into application logic.

## 6.2 Program

Represents a coherent program family such as Cub Scouts, Scouts BSA, or a user's custom learning framework.

Suggested fields:

- `id`
- `owner_id`
- `name`
- `slug`
- `program_type`
- `description`
- `status`: draft, active, archived
- `is_custom`
- `visibility`: private by default; future values may include shared or public
- `created_at`, `updated_at`

The initial UI does not need public sharing, but the model should not confuse a program with an individual award.

## 6.3 Award or AchievementDefinition

Represents a particular badge, rank, adventure, award, certificate program, or custom achievement.

Suggested fields:

- `id`
- `program_id`
- `name`
- `slug`
- `award_type`: merit badge, rank, adventure, award, certificate, custom, or extensible category
- `description`
- `category`, optional
- `official_identifier`, optional
- `eligibility_notes`, optional
- `status`
- `created_at`, `updated_at`

Do not assume every program has badges, ranks, or a progression hierarchy.

## 6.4 AwardVersion

Represents a specific, stable version of an achievement's requirement set.

Suggested fields:

- `id`
- `award_id`
- `version_label`
- `published_at`, optional
- `effective_from`, optional
- `effective_until`, optional
- `source_checked_at`, optional
- `source_status`: unverified, reviewed, verified, disputed, or other documented values
- `rights_status`: unknown, permission-confirmed, licensed, public-domain, user-authored, link-only, or other documented values
- `status`: draft, review, published, archived
- `change_summary`, optional
- `created_at`, `updated_at`

A published version should be immutable. Correcting a published version should create a new revision or version and record the relationship. Avoid modifying the requirements behind an existing user's active plan without their knowledge.

Publication date and effective date are different fields. Unknown dates must remain unknown, not guessed.

## 6.5 RequirementNode

Represents a requirement, subrequirement, group, or logical container within an `AwardVersion`.

Suggested fields:

- `id`
- `award_version_id`
- `parent_id`, nullable
- `sort_order`
- `display_number`, optional, preserving identifiers such as `1`, `1a`, or `3b(2)`
- `node_type`: atomic, group, note, or other explicitly defined type
- `text` or `authoritative_text`
- `text_origin`: official-source transcription, user-provided, app-authored, or other defined type
- `source_id`, optional
- `completion_logic`: all, any, choose_n, sequence, conditional, or single
- `completion_count`, optional, used for choose-N logic
- `condition_expression`, optional and constrained to a documented safe schema
- `estimated_effort`, optional and always labeled as an estimate
- `safety_notes`, optional
- `created_at`, `updated_at`

Do not store only a flat list of text strings. The schema must support nested structures and logical groups.

For official content, preserve the authorized wording, punctuation, numbering, quantities, named references, and alternative conditions as faithfully as the source and applicable rights allow. Keep app-authored explanation in a separate field or related record.

## 6.6 RequirementActionTag

A requirement can have one or more action tags to guide the workflow. Suggested tags:

- read
- discuss
- explain
- describe
- demonstrate
- show
- make
- build
- plan
- prepare
- conduct
- participate
- teach
- interview
- visit
- observe
- record
- log
- research
- reflect
- calculate
- identify
- compare
- other

These tags assist the interface and instruction engine. They must not replace the authoritative text or be treated as a sufficient description of the requirement's full meaning.

For complex requirements, action tags should be assigned and reviewed explicitly. Do not rely solely on automatic NLP classification.

## 6.7 SourceRecord

Records the provenance of requirements and educational content.

Suggested fields:

- `id`
- `title`
- `publisher_or_creator`
- `url`, optional
- `source_type`: official publication, official web page, user upload, external educational material, user-authored, or other
- `retrieved_at`, optional
- `publication_date`, optional
- `license_or_permission_notes`
- `attribution_requirements`, optional
- `access_notes`, optional
- `review_status`

Do not assume an online page is licensed for copying merely because it is publicly accessible.

## 6.8 LearningPlan

Represents one user's effort to complete an achievement using a specific `AwardVersion` or custom definition.

Suggested fields:

- `id`
- `user_id`
- `award_version_id`, nullable for a custom snapshot only if the custom model provides an equivalent immutable version reference
- `title_override`, optional
- `status`: planned, active, paused, personally_completed, abandoned, archived
- `started_at`, optional
- `target_date`, optional
- `personal_completed_at`, optional
- `notes`, optional
- `created_at`, `updated_at`

An active plan must remain pinned to its selected version. If a new official version appears, offer a deliberate comparison or migration workflow. Never migrate silently.

## 6.9 RequirementProgress

Tracks a user's relationship to a specific requirement instance within a learning plan.

Suggested fields:

- `id`
- `learning_plan_id`
- `requirement_node_id` or an immutable requirement snapshot/reference
- `status`: not_started, in_progress, awaiting_evidence, ready_for_review, personally_completed, needs_more_work, not_applicable_by_explicit_rule
- `prior_knowledge_claim`, boolean
- `prior_work_notes`, optional
- `learner_notes`, optional
- `self_attested_at`, optional
- `personally_completed_at`, optional
- `created_at`, `updated_at`

Do not expose `not_applicable_by_explicit_rule` as a way to arbitrarily skip official requirements. It should only be allowed when the requirement model explicitly defines a legitimate conditional or optional branch and the selected logic supports it.

## 6.10 EvidenceRecord

Suggested fields:

- `id`
- `requirement_progress_id`
- `evidence_type`: note, text_response, file, image, audio, video, external_link, time_log, witness_record, AI_practice_summary, or other defined type
- `title`, optional
- `description`
- `storage_key`, optional
- `external_url`, optional
- `created_at`
- `review_status`: unreviewed, learner_attested, feedback_received, human_observed, or other explicit status
- `reviewer_name_or_label`, optional
- `review_notes`, optional
- `retention_status`

`human_observed` must mean an actual human recorded an observation. AI must not set that status. Evidence records should preserve what happened and who recorded it, not claim more than the data supports.

## 6.11 LearningResource

Suggested fields:

- `id`
- `title`
- `creator_or_publisher`
- `url` or `storage_key`
- `resource_type`: article, book, video, image, diagram, worksheet, course, official guide, or other
- `description`
- `associated_requirement_ids`
- `source_id`, optional
- `rights_status`
- `last_reviewed_at`, optional
- `quality_notes`, optional
- `safety_review_status`, optional
- `accessibility_notes`, optional

Resources should be linked to requirements they actually support. Do not imply that a linked resource is official just because it appears in the app.

## 6.12 TutoringSession (optional AI module)

Suggested fields:

- `id`
- `user_id`
- `learning_plan_id`, optional
- `requirement_progress_id`, optional
- `agent_profile`
- `provider_name`
- `model_identifier`, optional
- `started_at`, `ended_at`
- `summary`, optional
- `saved_transcript_reference`, optional
- `source_references`
- `user_saved_session`, boolean

Minimize transcript retention. Prefer user-controlled saving and a concise session summary when it serves the educational purpose.

## 6.13 AchievementRecord and Certificate

An achievement record documents the platform's personal completion determination for a learning plan. It is not an official award.

Suggested fields:

- `id`
- `learning_plan_id`
- `achievement_type`: personal_learning_record or custom_certificate
- `display_title`
- `requirement_version_label`
- `completed_at`
- `completion_basis`: self-attested, evidence-documented, human-reviewed, or explicitly defined combination
- `certificate_storage_key`, optional
- `disclaimer_text_version`

Certificates must identify the platform as the issuer and state that the record is personal and unofficial when based on Scouting or another external organization's requirements.

## 6.14 AuditRecord

Track material changes to program definitions, published versions, completion states, sources, and administrative settings.

Suggested fields:

- `id`
- `actor_id`, optional for system actions
- `action`
- `entity_type`
- `entity_id`
- `timestamp`
- `change_summary`
- `before_after_reference`, where useful and safe

Audit logs should not unnecessarily retain sensitive evidence or full AI transcripts.

---

# 7. Requirement Logic and Completion Rules

This logic is central to correctness and must have automated test coverage.

## 7.1 Logical groups

Support, at minimum:

- **Single:** One requirement node with its own completion status.
- **All:** Every child requirement must be complete.
- **Any:** At least one child requirement must be complete.
- **Choose N:** The learner must complete the specified number of children.
- **Conditional:** Applicable child requirements depend on an explicit, documented condition.
- **Sequence:** Requirements must be completed in a defined order if the source actually requires that order.

Do not infer choose-N, all-of, or alternative semantics from the display number alone. The structure must be entered or validated from the source.

## 7.2 Progress calculation

- Derive progress from requirement logic; do not let users edit the overall completion percentage.
- Show completed, incomplete, conditional, and unresolved work distinctly.
- Do not treat opening a resource, watching a video, or chatting with an AI as completion by itself.
- Preserve the difference between a completed preparation activity and the requirement's actual requested action.
- If the source is unclear, flag the logic for review rather than guessing.
- A plan is personally complete only when its defined completion logic is satisfied and the learner records the personal-completion action.
- The app's personal-completion state is never equivalent to official award issuance.

## 7.3 Verbs and modalities

The interface should tailor prompts and evidence options based on action tags. Examples:

- `discuss`: open a discussion workspace; capture a learner-controlled summary; identify whether the specified conversation partner must be human.
- `demonstrate`: prompt for a real practical attempt and suitable evidence; make clear a text answer alone is not demonstration.
- `explain`: request the learner's own explanation and optionally provide formative feedback.
- `read`: offer the source, reading log, and comprehension support without claiming a summary replaces the required reading.
- `interview`: allow recording the interview date, participant role, questions or notes, and reflection, without fabricating the interview.
- `log`: support multiple dated entries and the stated interval or count.
- `teach`: support a lesson plan or evidence of instruction actually delivered to another person.

Action-specific flows are assistance. They must not silently add requirements that are absent from the official text.

---

# 8. Learning and EDGE Experience

## 8.1 Teaching module

Where appropriate, a learning module contains:

1. **Explain:** Context, terminology, prerequisites, and why the skill matters.
2. **Demonstrate:** A worked example, visual, diagram, video, or guided walkthrough.
3. **Guide:** Practice with feedback and troubleshooting.
4. **Enable:** Independent attempt, performance, or explanation.
5. **Optional reflection:** A prompt to note what was learned and what remains difficult. Reflection is not mandatory unless the actual requirement makes it mandatory.

## 8.2 Adapt to experience without altering requirements

Learners may indicate they already know a topic. The app may offer an optional diagnostic or let the learner proceed directly to the required activity.

The app must not force a beginner course when it is not needed. It must not remove explicit activities simply because a learner scores well on a quiz.

## 8.3 Accessibility and format options

Use plain language, navigable headings, keyboard support, visible focus states, adequate contrast, scalable text, captions/transcripts when available, and reduced-motion support. Target WCAG 2.2 AA.

Support save-and-resume. Avoid requiring all evidence to be audiovisual; provide appropriate alternatives when the requirement permits them and when the alternatives do not change the required outcome.

---

# 9. AI Tutors and Expert Agents

AI is an optional instructional layer. The application must remain fully usable if the configured model is offline or disabled.

## 9.1 Tutor modes

- **Discuss:** Have a substantive back-and-forth conversation about the topic.
- **Explain:** Teach a concept clearly with examples.
- **Practice:** Guide rehearsal or scenario-based practice.
- **Check understanding:** Ask questions and give formative feedback.
- **Prepare to demonstrate:** Help the learner understand steps, materials, and safety considerations before an independent attempt.
- **Review evidence:** Organize or comment on submitted evidence while accurately describing limits.

## 9.2 Discussion requirements

When the requirement says "discuss," the agent should conduct an actual dialogue, ask relevant questions, follow up on the answers, correct misunderstandings, and produce a short summary of what was discussed.

If the requirement explicitly names a person or class of human participants, an AI agent cannot be represented as satisfying that condition. AI practice may prepare the learner for the required human discussion, but the record must keep the two activities distinct.

## 9.3 Grounding and truthfulness

The agent must be given the exact requirement and version plus relevant approved instructional materials. It must:

- Clearly distinguish official text from explanations and AI suggestions.
- Avoid inventing official policies, requirement wording, source citations, or completion evidence.
- Identify uncertainty and conflicting sources.
- Link to sources when possible.
- Avoid asserting practical competence unless the evidence supports the limited claim being made.
- Defer to authoritative guidance for safety-sensitive material.
- Never sign an official approval or impersonate a qualified human counselor.

AI responses and summaries should not silently update a requirement definition or mark a requirement complete.

## 9.4 Provider abstraction

Implement a small provider interface that allows configuration of an external API or an existing local model service. Do not hard-code one provider into business logic.

Requirements:

- AI settings can be disabled.
- API keys come from environment variables or a protected settings mechanism, never source control.
- Model/provider outages produce an understandable error and leave learning records intact.
- Users can save or discard a session summary.
- Raw transcripts are not retained by default unless the user explicitly elects to save them.
- Do not send the entire personal database to a model. Send only the context needed for the current task.

Do not include a dedicated model-serving container in the default Compose stack. Configure an existing local model endpoint or enable a separate optional profile if there is a clear reason.

---

# 10. Resources and Video Support

## 10.1 General resource handling

Link resources to individual requirements and explain why they are relevant. Prefer authoritative, original, accessible, and maintained sources. Record when a resource was last checked and any known limitations.

The platform should distinguish:

- Official program material.
- Independently authored instructional material.
- External educational references.
- AI-generated explanation.
- User notes.

## 10.2 YouTube videos

A later milestone may discover or curate videos that show a relevant skill or explain a topic.

Store available metadata such as title, channel/creator, URL or video identifier, publication date if provided, associated requirements, review date, captions/transcript availability, and editorial notes.

Use authorized embeds or links. Do not download and rehost content, remove attribution, or label a video official without verifying that claim. If API-based search is implemented, follow the then-current API terms and quota rules.

A video may demonstrate a skill, but it is not proof that the learner personally performed it.

---

# 11. Official and Historical Content Governance

## 11.1 Content permissions

Public accessibility does not automatically grant permission to reproduce or redistribute program requirements, handbook text, images, badge artwork, logos, or instructional content.

Before seeding a public or redistributable catalog, identify the applicable license or obtain written permission where needed. Keep rights and provenance metadata attached to each source and version.

**Local internal-testing exception:** The owner may gather a small amount of requirement text (roughly one or two MB) into `source_reqs/` on the owner's own machine, to check that the app is being built as intended. This folder is gitignored and dockerignored. It must never be committed, baked into an image, included in seed data or fixtures, or be part of any shared or released build. Content used this way is treated as `rights_status: unknown` and `source_status: unverified`, and does not make it into the final product unless Section 11.1's permission rules are otherwise satisfied.

The application should support several source approaches:

- Manually entered user content.
- User-provided files the user is entitled to use.
- Properly licensed or permission-confirmed catalogs.
- Source links without reproducing protected text when appropriate.
- Public-domain material with recorded provenance.

Do not implement unauthorized scraping as a shortcut in the product. Automated import should be added only where the source and method permit it. Manual or scripted gathering into `source_reqs/` for local internal testing (see above) is the only exception, and such scripts must not be committed to ship as product features.

## 11.2 Source of truth

For every official program entry, record the source used, date checked, version/effective date if known, and review state. An uncertain or incomplete entry must be labeled as such.

AI may help compare versions or flag likely changes but must not publish official requirement text without source validation and human review.

## 11.3 Historical versions

The data model must support historical versions from the start, even if the initial deployment has only a few versions populated.

Historical version records must preserve:

- The exact known requirement text.
- Source provenance and rights status.
- Program and award identity.
- The year or period the source actually supports.
- Publication/effective dates only where known.
- Uncertainty notes where archival evidence is incomplete.

Do not invent missing historic text or imply a version is from a particular year without reliable evidence.

A learning plan pinned to a historical version should remain pinned. The app may compare it with another version but must not silently substitute current requirements.

---

# 12. User Experience and Navigation

## 12.1 Main navigation

Recommended initial navigation:

- **Discover:** Search programs and achievements.
- **My Learning:** Active and paused learning plans.
- **Create:** Create a custom program or achievement.
- **Resources:** Saved instructional resources, if needed as a separate destination.
- **Achievements:** Personal completion records and certificates.
- **Settings:** Profile, security, AI configuration, data export, and deletion.

Administrative catalog management can begin in Django Admin.

## 12.2 Discover/catalog screen

Display a clear title, source program, version availability, concise introduction, known prerequisites, activity types, resources, and content-review status. Estimated effort must be labeled as an estimate and omitted where it is not grounded.

The app should be navigable by a user who does not know Scouting terminology.

## 12.3 Requirement screen

Make the original requirement wording, its current status, and the next useful action immediately apparent. Separate official text from explanatory content and AI-generated material.

Avoid oversized progress dashboards or decorative badge collections that take space away from the work itself.

## 12.4 Progress summary

Show counts and clearly labeled states, such as:

- Completed personally.
- In progress.
- Awaiting evidence.
- Needs more work.
- Not yet started.

Do not rely on one percentage when it could imply that an award is complete despite mandatory outstanding requirements. If a percentage is shown, explain how it is calculated and display the unresolved required items.

## 12.5 Certificates

Personal certificates should include:

- Learner's chosen display name.
- Achievement/program name.
- Exact version or date range where known.
- Date the user recorded personal completion.
- What the record represents.
- App name as issuer.
- A clear statement that it is a personal, unofficial learning record and does not confer an official award or credential.

Do not imitate official award graphics, insignia, signatures, or certificates without permission.

---

# 13. Privacy, Security, and Data Management

## 13.1 Single-user-first design

The initial deployment is for one primary user. Use standard authenticated user records and permissions so that a future second-user mode is possible, but do not build social or collaboration features in the MVP.

No public self-registration by default. A private instance should be accessible only to authorized users.

## 13.2 Evidence privacy

Evidence can contain faces, voices, location data, documents, or third-party personal information. Before upload, explain that evidence is stored on the self-hosted instance. Make it easy to remove evidence and avoid public URLs for private uploads.

Do not use private notes, evidence, or conversations for model training. Do not transmit them to an external AI provider unless needed for the feature and consistent with the user's configuration and informed use.

## 13.3 Data export and deletion

The user should be able to export core personal data in a documented portable format. At a minimum, export learning plans, requirement statuses, notes, evidence metadata, achievement records, and source/version references. Evidence files may be included in a separate archive.

Deleting a record should respect referential integrity and clearly explain whether associated evidence will also be deleted. Provide an account-level deletion procedure appropriate for the initial single-user setup.

## 13.4 Backups and recovery

Document backups for both PostgreSQL and uploaded files. The backup procedure must not assume that backing up the database alone is sufficient.

Document restore steps and recommend periodically testing restore into a separate Compose project or a non-production environment. Avoid destructive restore scripts without a clear confirmation step.

---

# 14. Import and Export

## 14.1 Canonical structured import

JSON should be the canonical import format for program and requirement trees because it can preserve nesting, logic, alternatives, and source metadata.

The importer must:

- Validate against a documented schema.
- Support a dry-run mode.
- Report validation errors with precise paths, such as `requirements[2].children[0].text`.
- Avoid duplicate imports through explicit identifiers or an import key.
- Preview creates, updates, and conflicts before committing.
- Never overwrite a published version silently.
- Preserve original numbering and order.
- Require source and rights metadata for official-source imports or explicitly mark the record as unverified.

## 14.2 Export

Export custom program definitions and personal achievement data in a documented format that can be backed up and later imported again. Make clear which records are definitions and which are personal progress/evidence records.

## 14.3 Example JSON shape

The precise schema should be committed as a versioned file such as `docs/schemas/program-import.schema.json`. An illustrative example:

```json
{
  "schema_version": "1.0",
  "program": {
    "slug": "personal-astronomy",
    "name": "Personal Astronomy",
    "owner": "self",
    "program_type": "custom"
  },
  "award": {
    "slug": "backyard-astronomer",
    "name": "Backyard Astronomer",
    "award_type": "custom"
  },
  "version": {
    "label": "v1",
    "status": "draft",
    "source_status": "user_authored",
    "rights_status": "user_authored"
  },
  "requirements": [
    {
      "display_number": "1",
      "node_type": "atomic",
      "text": "Identify ten constellations visible from your location.",
      "action_tags": ["identify", "observe"],
      "completion_logic": "single",
      "evidence_expectations": ["observation_log", "learner_attestation"]
    },
    {
      "display_number": "2",
      "node_type": "atomic",
      "text": "Keep an observing journal on at least four separate nights.",
      "action_tags": ["record", "log", "observe"],
      "completion_logic": "single",
      "constraints": {
        "minimum_occurrences": 4
      },
      "evidence_expectations": ["dated_log_entries"]
    }
  ]
}
```

This is an example of custom content only. It is not an official Scouting requirement. The final schema must define allowed values and validation rules explicitly.

---

# 15. Testing Strategy

## 15.1 Unit tests

At minimum test:

- All-of, any-of, choose-N, conditional, sequence, and simple requirement logic.
- Nested requirement tree traversal.
- Progress derivation.
- Version pinning and immutability.
- Correct behavior when a new version is published.
- Import schema validation and duplicate handling.
- Source and rights metadata validation.
- Status transitions.
- Evidence permissions and upload validation.
- Certificate disclaimer and version details.
- AI provider disabled/unavailable behavior.

## 15.2 Integration tests

Test:

- Create a program, award, version, and nested requirements.
- Start a learning plan from a published version.
- Record prior knowledge without automatically completing the requirement.
- Add notes and evidence.
- Complete requirements according to their actual logic.
- Generate a personal achievement record.
- Export and re-import a custom program.
- Upgrade the app with a database migration and preserve existing records.

## 15.3 End-to-end acceptance scenarios

### Scenario A: A missed Cub Scout requirement

The user finds a Cub Scout program entry, chooses a specific version, starts a personal plan, reviews requirement text, completes activities, records evidence, and views a personal achievement summary. The app does not label the achievement as official advancement.

### Scenario B: A Scouts BSA merit badge

The user starts a merit badge plan. A requirement says to discuss a subject with a specified person. The user may practice with an AI tutor, but the app keeps that practice separate from the required human interaction. The plan cannot be marked personally complete while a mandatory activity remains outstanding.

### Scenario C: A practical demonstration

The user reads about a practical skill and watches a video. The requirement remains incomplete until the user records the actual required attempt or performance. The app does not claim that viewing the resource proves competence.

### Scenario D: Custom achievement

The user creates a private achievement, adds nested requirements and evidence expectations, saves it, starts a plan, completes the requirements, and generates a personal certificate.

### Scenario E: Historical version

The user starts a plan pinned to a historical version. A newer version is added. The original plan and evidence remain associated with the old version, and the app offers comparison without silently migrating the plan.

### Scenario F: AI provider outage

The AI service is disabled or unreachable. The user can still access program data, requirements, learning plans, notes, evidence, progress, export, and certificates.

---

# 16. Implementation Roadmap

Each phase should leave the application deployable. Do not implement a later phase before the previous phase's acceptance criteria are met unless the project owner changes the plan.

## Phase 0: Repository and design foundation

**Deliverables**

- Repository inspection and baseline report.
- Project scaffold using the agreed stack.
- Docker Compose deployment.
- PostgreSQL connection and migrations.
- Authentication and private single-user startup procedure.
- README, `.env.example`, health check, and backup/restore outline.
- Initial ADRs for stack, storage, and content-version model.

**Exit criteria**

- A clean checkout can be started following the README.
- The site is available in a browser.
- Persistent data survives container recreation.
- No app features depend on an external service.

## Phase 1: Generic program and requirement engine

**Deliverables**

- ProgramOwner, Program, Award, AwardVersion, RequirementNode, and SourceRecord model.
- Nested requirement display.
- Manually authored custom program and award creation.
- Version status and publication rules.
- Canonical JSON import schema and dry-run importer.
- Basic catalog browse and search.
- Tests for nested structures, imports, permissions, and version immutability.

**Exit criteria**

- The user can create a custom achievement with nested requirements.
- The user can import and validate a custom program from JSON.
- Published versions cannot be silently edited.
- Requirements are not hard-coded to Scouting-specific types.

## Phase 2: Personal learning workflow

**Deliverables**

- LearningPlan and RequirementProgress.
- Requirement action tags and evidence expectations.
- Learning-plan overview and requirement detail screens.
- Notes, prior-work declarations, and evidence uploads.
- Completion logic and status summaries.
- Personal completion record and unofficial certificate.
- Export of core personal records.

**Exit criteria**

- A complete custom learning path can be followed from plan creation to completion.
- Completion is calculated from requirement logic.
- Prior knowledge does not automatically mark requirements complete.
- Evidence privacy and account permissions are tested.

## Phase 3: Scouting-first catalog

**Deliverables**

- Program representation for Cub Scouts and Scouts BSA.
- Merit badge and rank/adventure data shapes.
- Initial validated catalog entries, based on available sources and applicable permissions.
- Exact source, version, and rights metadata for each published entry.
- User experience that makes incomplete catalog coverage visible.

**Exit criteria**

- Scouting concepts map cleanly to the generic engine without Scouting-specific hard-coded completion logic.
- Published entries have provenance and reviewed content status.
- The app never claims to provide a complete catalog unless that has been validated.

## Phase 4: AI tutoring and EDGE instruction

**Deliverables**

- Provider interface and configuration.
- Requirement-aware tutoring prompts.
- Discuss, explain, practice, understanding-check, and evidence-review modes.
- EDGE-based learning module patterns where appropriate.
- Source references and uncertainty behavior.
- User control of session summaries and retention.
- Tests confirming AI cannot create official approvals or falsely witness activities.

**Exit criteria**

- The app works with AI disabled.
- Tutor responses distinguish official text from instructional assistance.
- Discussion practice is not mistaken for a required human discussion.
- AI cannot silently change content or completion status.

## Phase 5: Resource and video features

**Deliverables**

- Resource records and requirement associations.
- Curated links and video metadata.
- Optional permitted video discovery.
- Editorial review status and stale-resource indicators.

**Exit criteria**

- Resource provenance is visible.
- Video viewing is not counted as learner demonstration.
- Embedding and API behavior comply with applicable current terms.

## Phase 6: Historical versions

**Deliverables**

- Populated historical versions where evidence and rights support them.
- Version comparison view.
- Explicit plan version selection.
- Change summaries and notification behavior.

**Exit criteria**

- An old plan retains its requirement version.
- Missing or uncertain historic content is not fabricated.
- Users can distinguish current from historical requirements.

## Phase 7: Additional programs and custom sharing

Only proceed when requested by the project owner.

Potential deliverables:

- More US Scouting programs.
- Other youth Scouting organizations and international programs.
- More complex award structures.
- Shared or published custom programs.
- Additional certificate templates and optional human review workflows.

Every additional program family requires source, content, rights, and semantics review.

---

# 17. Acceptance Criteria for the Overall MVP

The MVP is ready for regular personal use when all of the following are true:

1. It installs and runs through documented Docker Compose commands.
2. It uses persistent storage for database records and uploaded files.
3. Access is authenticated and public registration is disabled by default.
4. The owner can create programs and custom achievements.
5. Requirements can be nested and can express alternatives and required counts.
6. The owner can start, pause, resume, and complete a learning plan.
7. Every plan is tied to a stable requirement version.
8. Progress states are individual to each requirement and derived according to its logic.
9. Reading, discussion, demonstration, and practical activities are not treated as interchangeable.
10. Notes and evidence are stored privately and can be exported or deleted.
11. The app can issue clearly unofficial personal achievement records.
12. Core features remain available if no AI provider is configured.
13. Source, provenance, and rights status are recorded for imported program content.
14. Content coverage and uncertainty are visible to the user.
15. Tests cover critical requirement logic and version behavior.
16. Backup and restore instructions have been exercised at least once.

---

# 18. Open Decisions

Do not block Phase 0 unless a decision is required to start it. Record decisions and revisit when evidence is available.

1. **Final product name:** Keep “Merit Badge Counselor” as an internal name or choose a broader public-facing name after trademark and affiliation review.
2. **Official content source and rights:** Determine exactly which Scouting requirements and assets may be reproduced and how they may be imported. Local internal testing via `source_reqs/` is already allowed and does not wait on this decision; shipping or sharing any such content does.
3. **Initial catalog coverage:** Decide whether the first seeded catalog is a carefully validated subset or broader catalog coverage as available.
4. **AI provider:** Select an external API or an existing local inference endpoint. Core use must remain possible without it.
5. **Evidence file limits:** Set practical file-size limits and allowed types based on the private server's capacity.
6. **Certificate design:** Use a modest, printable personal record rather than imitating official award graphics.
7. **Historical seed data:** Choose initial years and awards only after reliable source material is identified.
8. **Multi-user support:** Keep the data model reasonably extensible, but defer public registration and sharing features until specifically requested.

---

# 19. Suggested Repository Layout

A suggested starting structure for a Django implementation:

```text
.
├── app/
│   ├── config/                 # Django project settings and URL routing
│   ├── accounts/
│   ├── programs/
│   ├── requirements/
│   ├── learning/
│   ├── evidence/
│   ├── resources/
│   ├── tutoring/
│   ├── achievements/
│   ├── audit/
│   ├── templates/
│   └── static/
├── docs/
│   ├── decisions/              # Architecture Decision Records
│   ├── schemas/
│   ├── product-spec.md         # This document or a copy of it
│   └── operations.md
├── tests/
├── scripts/
├── .dockerignore
├── .env.example
├── Dockerfile
├── compose.yaml
├── manage.py
├── pyproject.toml
└── README.md
```

Adjust the layout to fit a repository that already exists. Avoid creating empty apps or directories before their functionality is needed.

---

# 20. First Task for the Coding Agent

Do not start by importing the full Scouting catalog or building AI agents.

The first implementation task should be **Phase 0 only**:

1. Inspect the repository, if it exists.
2. Confirm whether Django and PostgreSQL are appropriate based on the existing state.
3. Create the minimal deployable application and Compose configuration.
4. Add authenticated access and a reliable first-user bootstrap path.
5. Add persistent storage, health checks, environment configuration, and documentation.
6. Verify the application can be started, stopped, and recreated without data loss.
7. Summarize the files created, tests run, commands to start the service, and known limitations.

Do not implement later phases until Phase 0 is working and the project owner has reviewed the result.

---

# Appendix A: Short Project Brief for New LLM Sessions

Use this brief when starting a new coding session. The full specification remains authoritative.

> Build a private, self-hosted, browser-based personal achievement and learning platform, deployed with Docker Compose. The primary personal use is to work through Scouting America Cub Scout requirements, Scouts BSA rank requirements, and merit badges that the owner missed or wants to revisit. The underlying engine must remain program-agnostic and support custom achievements and versioned requirements.
>
> Use a simple modular Django monolith with PostgreSQL by default. Serve a responsive website. Do not build native applications, public registration, social features, a SaaS service, or a microservice architecture. Core functionality must work without AI or any external cloud service.
>
> Preserve authoritative requirement wording and source/version metadata. Represent nested requirements, alternatives, counts, durations, and action types explicitly. Keep requirement definitions separate from personal progress and evidence. Do not equate reading, watching a video, or chatting with an AI with actually performing a required activity. Historical versioning must be supported by the data model from the beginning. The app records personal learning and does not confer official Scouting awards.
>
> Implement the project in phases. Begin with repository inspection and Phase 0 deployment foundation only. Keep the app runnable, write tests, document decisions, and do not expand scope without approval.
