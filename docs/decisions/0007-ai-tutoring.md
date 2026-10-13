# 0007 - AI tutoring

Status: Proposed (decided under the owner's Phase 4 approval; the owner may change it)

## Context
Phase 4 adds an optional AI tutor. `PLAN.md` §18 left the provider open. The owner chose an OpenAI-compatible endpoint, with settings in the Settings tab and an encrypted key.

## Decision
- **Provider.** One adapter, `OpenAICompatibleProvider`, calls `POST {base_url}/chat/completions` through `httpx`. It covers Ollama, llama.cpp, vLLM, LM Studio and many hosted APIs. Another provider is another class with the same `complete(system, messages)` method. No provider SDK.
- **Settings.** One database row, edited by admins in Settings. The key is encrypted with a key derived from `DJANGO_SECRET_KEY` (a different HKDF label from OIDC). It is write-only in the UI. `AI_*` variables pre-fill the row once. The tutor is off by default.
- **Grounding.** The model gets the requirement text, its origin label (official or not), the version, safety notes, the parent requirement text, and the action tags. In review mode it also gets up to 10 evidence titles and descriptions, cut to 600 characters each. It gets no files and nothing from other plans or users.
- **Guardrails.** The system prompt forbids declaring anything complete, passing or demonstrated, and says the tutor cannot stand in for a named person or a practical task. The `tutoring` service code never imports or calls learning, evidence or achievement writers. Tests check that a session changes no progress, plan or evidence. Model text is rendered escaped. Learner and evidence text is marked untrusted in the prompt.
- **EDGE.** Each mode maps to an EDGE stage in its prompt (Explain, Demonstrate, Guide, Enable). It is a style, not a gate. It never waives a stated condition.
- **Retention.** The transcript lives on the open session only. After the session ends the learner keeps the summary, keeps summary and transcript, or deletes it all. Open or undecided sessions are purged after one day. The summary is not an `EvidenceRecord`. The existing `ai_practice_summary` evidence type stays unused by the tutor.
- **Limits.** 2000 characters per message, 30 learner messages per session, the last 20 messages as history, a 60 second timeout. Calls are synchronous. No queue.

## Consequences
- One new table pair and no new dependency.
- Changing `DJANGO_SECRET_KEY` makes the stored key unreadable. The admin enters it again.
- Follow-up ideas, not built: streaming replies, per-user rate limits, an admin-written interpretation text per requirement, saving a summary as a note by choice, a second provider adapter.
