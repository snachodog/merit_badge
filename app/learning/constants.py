"""Settings-style constants for the learning workflow. Edit here to adjust the rules.

Evidence needed before a requirement can be personally completed
-----------------------------------------------------------------
A requirement tagged with one of the action tags below cannot be marked
personally completed until ONE of these is true:

1. It has at least one evidence record whose type is listed for one of its tags, or
2. The learner recorded an explicit attestation ("I did this") on the requirement.

Rules that are not negotiable:
- Reading a resource and AI sessions never count. The type `ai_practice_summary`
  is therefore never in any list below, and is also rejected in code.
- A text answer alone is not a demonstration (PLAN.md section 7.3), so
  `demonstrate` and `show` list no text types.
- Tags not listed here (for example `read`, `reflect`, `identify`) need no
  evidence. The learner still has to mark them complete themselves.
- These are guides for the learner. They never add requirements that the
  requirement text does not contain. The attestation is always the way out.

Values must match `evidence.models.EvidenceRecord.EvidenceType`.
"""

_PRACTICAL = ("image", "video", "audio", "file", "witness_record")

EVIDENCE_TYPES_BY_TAG = {
    "demonstrate": _PRACTICAL,
    "show": _PRACTICAL,
    "make": _PRACTICAL + ("time_log",),
    "build": _PRACTICAL + ("time_log",),
    "conduct": _PRACTICAL + ("time_log", "note"),
    "participate": _PRACTICAL + ("time_log", "note"),
    "teach": _PRACTICAL,
    "interview": ("note", "text_response", "audio", "file", "witness_record"),
    "discuss": ("note", "text_response", "audio", "witness_record"),
    "visit": _PRACTICAL + ("time_log", "note"),
}

# Never counts toward completion, whatever the tag.
NEVER_COUNTS = ("ai_practice_summary",)
