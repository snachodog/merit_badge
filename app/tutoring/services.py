"""Tutoring rules: settings, sessions and what the model may see.

This module never touches progress, evidence or achievements. It cannot mark
anything complete (PLAN.md 0.2, 9.3). A session is a study aid, not evidence.
"""
import os
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.services import record_audit

from . import crypto, prompts, providers
from .models import AISettings, TutoringSession

MAX_MESSAGE_CHARS = 2000
MAX_USER_MESSAGES = 30
HISTORY_WINDOW = 20
EVIDENCE_LIMIT = 10
EVIDENCE_TEXT_CHARS = 600
STALE_AFTER = timedelta(days=1)


class TutorError(Exception):
    """A refused or failed tutoring step. The message is safe to show to the learner."""


# Settings ---------------------------------------------------------------------------


def _env_bool(name):
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def get_settings():
    """Return the single settings row. The first access pre-fills it from AI_* variables."""
    row = AISettings.objects.filter(pk=1).first()
    if row:
        return row
    row = AISettings(
        pk=1,
        base_url=os.environ.get("AI_BASE_URL", "").strip(),
        model=os.environ.get("AI_MODEL", "").strip(),
        api_key_encrypted=crypto.encrypt(os.environ.get("AI_API_KEY", "")),
    )
    row.enabled = _env_bool("AI_ENABLED") and bool(row.base_url and row.model)
    try:
        with transaction.atomic():
            row.save(force_insert=True)
    except IntegrityError:
        row = AISettings.objects.get(pk=1)
    return row


def key_is_usable(row):
    """True if there is no key (local models) or the stored key can be read."""
    return not row.api_key_encrypted or crypto.decrypt(row.api_key_encrypted) is not None


def is_configured(row):
    return bool(row.base_url and row.model and key_is_usable(row))


def is_available():
    row = get_settings()
    return row.enabled and is_configured(row)


def save_settings(actor, data):
    row = get_settings()
    row.enabled = bool(data["enabled"])
    row.base_url = data["base_url"].strip().rstrip("/")
    row.model = data["model"].strip()
    if data.get("clear_api_key"):
        row.api_key_encrypted = ""
    elif data.get("api_key"):
        row.api_key_encrypted = crypto.encrypt(data["api_key"])
    row.updated_by = actor
    row.save()
    record_audit("ai_settings_changed", actor, enabled=row.enabled)
    return row


def provider_for(row):
    return providers.OpenAICompatibleProvider(row.base_url, row.model, crypto.decrypt(row.api_key_encrypted))


def test_connection(row):
    """Return (ok, message). Sends one tiny request. Nothing is stored."""
    if not is_configured(row):
        return False, "Enter and save a URL and model first."
    try:
        provider_for(row).complete("Reply with the single word OK.", [{"role": "user", "content": "Test"}], max_tokens=10)
    except providers.ProviderError as exc:
        return False, str(exc)
    return True, "The AI endpoint answered."


# Context ----------------------------------------------------------------------------


def build_context(progress):
    """The only data the model sees: this requirement, its version, and (review mode) its evidence."""
    node = progress.requirement_node
    version = progress.learning_plan.award_version
    origin = "official text" if node.text_origin == "official_source" else "not official text"
    evidence = [
        {
            "type": e.get_evidence_type_display(),
            "review": e.get_review_status_display(),
            "title": e.title[:120],
            "description": e.description[:EVIDENCE_TEXT_CHARS],
        }
        for e in progress.evidence_records.order_by("-created_at")[:EVIDENCE_LIMIT]
    ]
    return {
        "award": str(version.award),
        "version": version.version_label,
        "number": node.display_number,
        "text": node.text,
        "origin_label": origin,
        "parent_text": node.parent.text if node.parent_id else "",
        "safety_notes": node.safety_notes,
        "tags": list(node.action_tags.values_list("tag", flat=True)),
        "evidence": evidence,
        "source_title": node.source.title if node.source_id else "",
    }


def source_references(context):
    refs = [{
        "kind": "requirement",
        "label": "Requirement %s, %s, version %s (%s)" % (
            context["number"], context["award"], context["version"], context["origin_label"]),
    }]
    if context["source_title"]:
        refs.append({"kind": "source", "label": "Source record: " + context["source_title"]})
    if context["evidence"]:
        refs.append({"kind": "evidence", "label": "%d evidence description(s), text only" % len(context["evidence"])})
    return refs


# Sessions ---------------------------------------------------------------------------


def purge_stale(user):
    """Remove sessions the learner left open or undecided for a day. Kept sessions stay."""
    TutoringSession.objects.filter(
        user=user, status__in=[TutoringSession.Status.OPEN, TutoringSession.Status.ENDED],
        started_at__lt=timezone.now() - STALE_AFTER,
    ).delete()


def start_session(user, progress, mode):
    if mode not in TutoringSession.Mode.values:
        raise TutorError("Choose one of the tutor modes.")
    row = get_settings()
    if not (row.enabled and is_configured(row)):
        raise TutorError("The AI tutor is off. The rest of the app works without it.")
    purge_stale(user)
    context = build_context(progress)
    return TutoringSession.objects.create(
        user=user, progress=progress, mode=mode, provider_name=providers.OpenAICompatibleProvider.name,
        model_identifier=row.model, source_references=source_references(context),
    )


def _call(session, extra_user=None):
    row = get_settings()
    if not (row.enabled and is_configured(row)):
        raise TutorError("The AI tutor is off. The rest of the app works without it.")
    context = build_context(session.progress)
    history = list(session.transcript)[-HISTORY_WINDOW:]
    if extra_user:
        history.append({"role": "user", "content": extra_user})
    try:
        return provider_for(row).complete(prompts.system_prompt(session.mode, context), history)
    except providers.ProviderError as exc:
        raise TutorError(str(exc))


def send_message(session, text):
    """Add the learner's message and the tutor's reply. On failure nothing is added."""
    if session.status != TutoringSession.Status.OPEN:
        raise TutorError("This session has ended.")
    text = (text or "").strip()
    if not text:
        raise TutorError("Write a message first.")
    if len(text) > MAX_MESSAGE_CHARS:
        raise TutorError("Keep each message under %d characters." % MAX_MESSAGE_CHARS)
    if sum(1 for m in session.transcript if m["role"] == "user") >= MAX_USER_MESSAGES:
        raise TutorError("This session is long enough. End it and start a new one if you want to continue.")
    reply = _call(session, extra_user=text)
    session.transcript = [*session.transcript, {"role": "user", "content": text}, {"role": "assistant", "content": reply}]
    session.save(update_fields=["transcript"])
    return reply


def end_session(session):
    """Close the session and ask for a summary. A failed summary leaves the session ended without one."""
    if session.status != TutoringSession.Status.OPEN:
        return session
    summary = ""
    if session.transcript:
        try:
            summary = _call(session, extra_user=prompts.SUMMARY_REQUEST)
        except TutorError:
            summary = ""
    session.summary = summary
    session.status = TutoringSession.Status.ENDED
    session.ended_at = timezone.now()
    session.save(update_fields=["summary", "status", "ended_at"])
    return session


def keep_session(session, save_transcript=False):
    if session.status != TutoringSession.Status.ENDED:
        raise TutorError("End the session before you keep it.")
    session.status = TutoringSession.Status.KEPT
    session.transcript_saved = bool(save_transcript)
    if not save_transcript:
        session.transcript = []
    session.save(update_fields=["status", "transcript_saved", "transcript"])
    return session


def discard_session(session):
    session.delete()
