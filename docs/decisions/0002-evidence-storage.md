# 0002 - Evidence and upload storage

Status: Accepted (Phase 0 scope); revisit in the evidence phase

## Context
Evidence files are private personal data (PLAN.md sections 5.3, 5.5, 13.2) and must
persist independently of container lifecycles and stay out of public static paths.

## Decision
- Uploads are stored on the local filesystem under `DJANGO_MEDIA_ROOT`
  (`/data/media` in the container), mounted from the named volume `media`.
- This path is separate from `STATIC_ROOT`; there is deliberately no `MEDIA_URL` and
  no web-server route to media. Files will be served only through authenticated
  Django views that check ownership.
- Access goes through Django's storage API so an S3-compatible backend can be
  substituted later without changing callers.
- Later phases must validate content type, extension, size, and generate server-side
  file names to prevent path traversal.
- Backups must include this volume together with the database (docs/operations.md).

## Consequences
Simple and portable for one host. No deduplication, quotas, or off-host durability
until a backup routine or object storage is adopted.
