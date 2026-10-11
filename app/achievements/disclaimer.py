"""Versioned certificate wording (PLAN.md 6.13 and 12.5).

An achievement record stores the version it was issued under, so old records
keep their original wording. To change the wording, add a new version here,
set CURRENT_VERSION to it, and never edit an older entry.

Placeholders: {issuer} is the app name.
"""

CURRENT_VERSION = "1"

DISCLAIMERS = {
    "1": (
        "This is a personal, unofficial learning record. It was issued by {issuer}, a private "
        "self-hosted app, and records what the learner says they completed. "
        "It does not confer an official award, rank, badge, or credential. "
        "It is not issued, endorsed, or recognized by Scouting America or any other organization."
    ),
}


def disclaimer_text(version, issuer):
    """Return the wording for `version`. Unknown versions raise KeyError, never fall back."""
    return DISCLAIMERS[version].format(issuer=issuer)
