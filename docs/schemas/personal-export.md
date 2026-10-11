# Personal data export format

Version 1.0. Source: `app/config/core/export.py`. Download from **Settings**.

The export has two files. Both hold only the signed-in account's data.

- `personal-export-YYYYMMDD.json`: records and metadata.
- `evidence-files-YYYYMMDD.zip`: the uploaded evidence files.

The data is a personal, unofficial learning record. It is not an official award.

## JSON file

All timestamps are ISO 8601. Missing values are `null`. The file is UTF-8.

Top-level fields:

- `format`: always `merit-badge-personal-export`.
- `format_version`: `"1.0"`. The major number changes if a field is removed or renamed.
- `exported_at`, `app_name`, `notice`.
- `account`: `username`, `display_name`.
- `learning_plans`: list of plans (below).
- `achievements`: list of achievement records (below).

### Learning plan

- `id`, `title`, `status`, `started_at`, `target_date`, `personal_completed_at`, `notes`.
- `condition_answers`: answers to conditional requirements, as stored.
- `version`: the source and version reference. Fields: `award_version_id`, `version_label`,
  `award_name`, `program_name`, `program_owner`, `is_custom_program`, `published_at`,
  `effective_from`, `effective_until`, `source_status`, `rights_status`.
- `status_log`: list of `from_status`, `to_status`, `changed_at`, `note`.
- `requirements`: one entry per requirement (below).
- `achievement_id`: id of the plan's achievement record, or `null`.

### Requirement entry

- `requirement_id`, `display_number`, `text`, `text_origin`.
- `source`: `title`, `publisher_or_creator`, `url`, `source_type`, `review_status`, or `null`.
- `status`: the learner's progress status.
- `prior_knowledge_claim`, `prior_work_notes`, `learner_notes`.
- `self_attested_at`, `personally_completed_at`.
- `evidence`: list of evidence metadata.

Prior knowledge and self-attestation are claims. They do not mean the requirement is complete.

### Evidence metadata

- `id`, `evidence_type`, `title`, `description`, `external_url`, `created_at`.
- `review_status`, `reviewer_name_or_label`, `review_notes`, `retention_status`.
- `file`: `null`, or `original_filename`, `content_type`, `size_bytes`, `sha256`, `archive_path`.
  `archive_path` is the file's path inside the zip.

### Achievement record

`id`, `learning_plan_id`, `achievement_type`, `display_title`, `program_name`,
`requirement_version_label`, `completed_at`, `completion_basis`, `disclaimer_text_version`,
`learner_display_name`, `issuer_name`, and `official` (always `false`).

## Zip file

- `manifest.json`: `format` (`merit-badge-personal-export-evidence`), `format_version`,
  `exported_at`, `files` (list of `evidence_id`, `path`, `sha256`), and `missing_evidence_ids`
  (records whose file could not be read).
- `evidence/plan-<plan id>/<evidence id>-<clean file name>`: one file per upload.

To check a file, compare its SHA-256 hash with `sha256` in the JSON or the manifest.
