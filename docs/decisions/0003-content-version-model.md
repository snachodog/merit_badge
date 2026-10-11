# 0003 - Content version model

Status: Accepted by owner (to be implemented in Phase 1; no schema exists in Phase 0)

## Context
Requirements change over time and PLAN.md (sections 6, 11) requires faithful,
source-attributed wording, historical versions, and a strict separation between
shared definitions and personal progress.

## Decision
- An Award (stable identity) has many AwardVersions; each version owns its own tree of
  RequirementNodes with source metadata (SourceRecord) and explicit logic/count fields.
- A version is draft until published; published versions are immutable. Corrections
  create a new version rather than editing wording in place.
- Personal records (LearningPlan, RequirementProgress, EvidenceRecord) reference a
  specific AwardVersion/RequirementNode and never store progress on the definition.
- Imports are JSON, dry-run first, and always produce new draft versions.

## Consequences
Historical plans remain valid when requirements change. Costs extra rows and a
publication workflow. Details will be refined when the Phase 1 models and tests land; any
change will be recorded here.

## Future work (out of scope)
Determining whether historical requirements satisfy newer ones, and carrying progress forward, is deferred (see PLAN.md roadmap candidates). The version model keeps plans pinned and non-destructive so such a mapping can be added later.
