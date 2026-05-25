# Phase 18: AI Notice Response Drafting (BYOK) - Context

**Phase Goal:** A reviewer asks the system to draft a reply for an open notice; the BYOK provider returns a markdown letter that respects the notice context, the Phase 17 extracted fields, and any free-text guidance from the user. The draft is preview-only at the service layer. Persisting goes through the existing Phase 12 versioned-draft + 4-stage approval flow.

**Status:** SHIPPED 2026-05-25
**Architecture register:** product (compliance app UI), not marketing
**Builds on:** Phase 9 (RBAC, audit immutability, RLS), Phase 12 (notice_responses + versions + approvals), Phase 16 (BYOK provider abstraction, scope-locked SYSTEM prompt), Phase 17 (extracted_fields envelope as context)

## Boundary

**In scope:**
1. New service `response_drafter_service.draft_response_for_notice(db, notice, user_id, user_guidance)` that calls Phase 16 `build_provider` with a draft-specific user prompt and returns a markdown draft body plus telemetry.
2. New prompt module `response_drafter_prompt.py` holding the draft template, character cap on user guidance (800 chars), and the max response token budget (1400 tokens).
3. New endpoint `POST /api/compliance/ai/notice-response-draft/{notice_id}` gated by `NOTICE_DRAFT_RESPONSE`. Rate limited to 12/minute per the Phase 17 extract-preview parity (same cost profile, same provider call cardinality).
4. Audit row `notice_ai_draft` per call, PII-redacted (provider, model, tokens, latency, body SHA-256, guidance SHA-256, list of extracted field KEYS only). No raw draft text, no guidance text.
5. End-to-end smoke `scripts/smoke_phase18_v20.py` covering 10 checks: service imports, endpoint registration, permission grants, BYOK 412 path, real provider call, audit redaction, guidance round-trip, audit immutability, RLS isolation, idempotent cleanup.
6. Reuses the Phase 16 `SCOPE_LOCK_SYSTEM` prompt via `ai_service._run`, so out-of-scope drift returns the same OUT_OF_SCOPE sentinel and surfaces as HTTP 422.

**Out of scope:**
- No migration. `notice_response_versions.metadata_json` (JSONB, Phase 12) is the canonical home for the AI draft provenance when the caller decides to persist; persistence itself is the caller's responsibility (POST /responses).
- No frontend update in this slice. The endpoint is callable from the existing response editor; UI integration is queued for the next session.
- No automatic version creation. The service is preview-only; the user accepts or edits before saving.
- No multi-draft fan-out (generate 3 variants, pick one). Single-shot only.

## Design Decisions

### D-01: Service is the persistence boundary, not the API.
The service returns the draft envelope. The router is the only place that touches DB write paths. Unit tests can exercise drafting against a MagicMock notice without DB. Future surfaces (CLI, Celery batch) reuse the same service.

### D-02: Reuse Phase 16 SCOPE_LOCK_SYSTEM.
The SYSTEM prompt is unchanged. Any drift toward marketing prose, generic legal advice, or out-of-domain output is rejected by the OUT_OF_SCOPE sentinel that protects the existing 5 Phase 16 surfaces.

### D-03: User guidance capped at 800 chars.
Enough to say "be more terse" or "cite Section 17(5)". Too short to inject a competing prompt or paste an entire competing draft. Truncated BEFORE hashing so the audit trail records exactly what the prompt saw.

### D-04: Max response tokens = 1400.
Empirically covers a 300-700 word notice reply at safe margin. Lower than the 2048 ceiling on Phase 17 extraction because the output here is prose, not a JSON envelope.

### D-05: Permission is `NOTICE_DRAFT_RESPONSE`.
Granted to legal_team, ca_consultant, staff. NOT compliance_head (approver), auditor (read-only), CFO (approver), finance_team (read-only on tax notices). Compliance_head can still trigger drafts by switching to one of the drafter roles or asking a drafter to do it; this matches the existing Phase 12 approval-chain separation of duties.

### D-06: Audit hashes both the draft body AND the guidance.
`body_sha256` lets a future audit verify that the persisted NoticeResponseVersion matches what the model emitted, even after edits, by recomputing. `guidance_sha256` records exactly what instruction the user gave the model without storing the guidance text. Two calls with different guidance get distinct audit rows even if the draft body happens to land identical.

### D-07: Drafts always include the notice context.
The prompt embeds a JSON projection of the notice: number, authority, type, dates, amounts, legal sections, risk tier, and the post-validation extracted_fields summary from Phase 17. The model is told to quote financial figures verbatim and cite legal sections without invention.

### D-08: Insufficient context produces a sentinel, not a fabricated reply.
The prompt instructs the model to return exactly `INSUFFICIENT_CONTEXT` when it cannot draft a competent reply. The smoke does not explicitly test this; it is a defensive prompt rule, not a contract gate.

### D-09: No accepted-edits feedback loop in v2.0.
A future v2.1 could compare the draft body to the eventual submitted body and use the diff as a signal for prompt tuning. Out of scope.

### D-10: 12/minute rate limit per tenant per IP.
Matches Phase 17. Cost profile is the same. A future Phase 18 v2.1 should switch to a per-`client_id` rate-limit key once the broader rate-limiter refactor lands; tracked in the open CodeQL items.

## Success Criteria

1. A user with `NOTICE_DRAFT_RESPONSE` on the active client can POST `/api/compliance/ai/notice-response-draft/{notice_id}` and receive a non-empty markdown draft body within 10 seconds for a 14-field-extracted notice.
2. The user can supply `user_guidance` up to 800 chars; the same notice with different guidance produces audit rows with different `guidance_sha256` hashes.
3. A tenant without an `AICredential` configured receives HTTP 412 with a structured detail pointing at `/dashboard/settings/ai-credentials`.
4. Every draft call writes exactly one `notice_ai_draft` audit row with provider, model, latency, tokens, body SHA-256, guidance SHA-256, and extracted-field key list. No raw draft text, no raw guidance text.
5. Phase 9 immutability trigger refuses any UPDATE or DELETE attempt on draft audit rows.
6. RLS isolation holds: an audit row for client A is invisible to a session bound to client B.
7. Smoke (`scripts/smoke_phase18_v20.py`) passes 10 of 10 checks end to end against a real provider call.

## Requirements

- **DRAFT-01:** Per-tenant BYOK provider call (Phase 16 AICredential reused)
- **DRAFT-02:** Draft-specific prompt module with guidance cap and response token cap (D-03, D-04)
- **DRAFT-03:** Permission gate at NOTICE_DRAFT_RESPONSE (D-05)
- **DRAFT-04:** Audit row per call with hashed body + guidance + key list, no raw text (D-06)
- **DRAFT-05:** Tenant-without-credential graceful path (HTTP 412)
- **DRAFT-06:** RLS isolation on the audit row (Phase 9 inheritance)
- **DRAFT-07:** Immutability of draft audit rows (Phase 9 inheritance)
- **DRAFT-08:** Out-of-scope sentinel surfaces as HTTP 422 (Phase 16 inheritance)
- **DRAFT-09:** Rate limit 12/minute per tenant per IP (D-10)

## v2.1 Deferrals

- Frontend integration: AI-draft button in the response editor.
- Persist as NoticeResponseVersion in one round-trip (currently the caller composes draft + save).
- Active-learning feedback loop using accepted-vs-drafted diffs.
- Multi-variant fan-out (generate 3, pick one).
- Per-client_id rate-limit key (broader rate-limiter refactor).
