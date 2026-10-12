# Scouting catalog structure

Scouting uses the generic model. No code branches on Scouting concepts.

| Scouting term | Stored as |
|---|---|
| Scouting America | `ProgramOwner` (a named source, not a claim of recognition) |
| Cub Scouts, Scouts BSA | `Program` |
| Merit badge, rank, adventure | `Award` with `award_type` `merit_badge`, `rank` or `adventure` |
| Requirement list | `AwardVersion` with `RequirementNode` rows |
| "Do 2 of these 5" | node with `completion_logic` `choose_n` and `completion_count` |

Shapes are listed in `app/programs/scouting.py`. Use `Award.category` for a rank or den level.

## Provenance and validation

- Each version carries a version label, `source_status` and `rights_status`.
- Each requirement node cites a `SourceRecord` with a URL.
- An entry is validated if its newest published version is reviewed or verified, has known
  rights, and cites a source on every node.
- `programs.coverage.program_coverage(program)` returns counts and the reasons a catalog is
  incomplete. `catalog_may_be_called_complete(program)` returns False unless the owner set
  `catalog_validated_complete`, the expected count is known, and all entries are validated.

## Follow-up

- Show `ProgramCoverage.label` and `reasons` on the catalog and program pages.
- Real entries need owner review of sources and rights before they are published.
