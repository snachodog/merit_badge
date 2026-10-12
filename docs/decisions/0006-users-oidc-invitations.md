# 0006 - Roles, OIDC sign-in and invitations

Status: Proposed (decided by the lead session under the owner's Phase 3b approval; the owner may change it)

## Context
Phase 3b adds a second user, OIDC sign-in and invitation links. The app stays self-hosted and invitation-only.
`PLAN.md` §18 left three points open: where OIDC settings live, which library to use, and whether a user can link an OIDC identity to a password account.

## Decision
- **Roles.** Two roles: `admin` and `user`. A new `accounts` app holds a profile with the role. Django `is_staff` and `is_superuser` stay as they are. The first user (bootstrap) is an admin.
- **Admin only:** the Settings sections Users, Invitations and OIDC, plus catalog authoring (create program, import JSON, edit and publish versions). **Users:** browse the catalog, run their own plans, keep their own evidence and achievements.
- **Privacy.** Admins have no route to another user's evidence, notes or plans. User management shows names, roles and status only.
- **Library.** Use Authlib (`authlib`) for the OIDC authorization-code flow with PKCE and discovery. Add `httpx` only if Authlib needs it.
- **OIDC settings live in the database**, one row, edited in Settings. A Settings tab needs live edits and a restart would be a poor fit. The client secret is encrypted at rest with a key derived from `DJANGO_SECRET_KEY` and is write-only in the UI. Environment variables may pre-fill the row on first start (`OIDC_*` in `.env.example`).
- **Linking.** An OIDC identity (issuer + subject) links to a user in two ways only: by accepting an invitation, or by a signed-in user choosing "Link OIDC" in Settings. OIDC never creates an account without an invitation. Matching by e-mail alone is not allowed.
- **Lockout safety.** Password sign-in always works. The last active admin cannot be demoted, deactivated or deleted.
- **Invitations.** A token of at least 32 random bytes. Only a hash is stored. Each link has a role, an expiry (admin chooses; default 7 days), and a single use. The full link shows once, at creation.
- **Audit.** Sign-in method changes, role changes, deactivation and invitation use write an audit record.

## Consequences
- One new dependency (Authlib, plus `cryptography` for the secret). Both are pinned.
- If `DJANGO_SECRET_KEY` changes, the stored OIDC secret cannot be read. The admin enters it again. Document this in the README.
- Existing single-user installs keep working. Their first user becomes the admin by migration.
- Catalog authoring becomes admin only. A user who needs a custom program asks an admin.
