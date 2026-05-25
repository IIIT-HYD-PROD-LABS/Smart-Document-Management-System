# Plan 18-01 Summary: AI Notice Response Drafting (BYOK)

**Status:** SHIPPED 2026-05-25
**Phase:** 18
**Wave:** single-pass v2.0
**Result:** Phase 18 backend + smoke ships. Smoke 10 of 10 PASS via live Gemini.

## Delivered

### 1. Prompt module - `backend/app/compliance/services/response_drafter_prompt.py`

Holds the draft-specific user-prompt template, the 800-char guidance cap, and the 1400-token response budget. Reuses Phase 16 SCOPE_LOCK_SYSTEM via `ai_service._run`. The prompt embeds the notice as a structured JSON projection (number, authority, type, dates, amounts, legal sections, risk tier, post-validation extracted_fields) and instructs the model to quote figures verbatim, cite sections without invention, and return the sentinel `INSUFFICIENT_CONTEXT` when it cannot draft competently.

### 2. Service - `backend/app/compliance/services/response_drafter_service.py`

`draft_response_for_notice(db, notice, user_id, user_guidance="")` resolves the tenant's Phase 16 AICredential (raises `ResponseDraftCredentialMissingError` -> HTTP 412 if missing), calls the provider with the draft prompt, captures latency + chars in/out, and writes one `notice_ai_draft` audit row with the PII-redacted shape from D-06. Returns the draft envelope shaped as `{draft_body_markdown, model, tokens_in, tokens_out, latency_ms, extracted_fields_used}`. Persistence is the caller's responsibility (POST /responses).

### 3. Endpoint - `POST /api/compliance/ai/notice-response-draft/{notice_id}`

Added to the existing Phase 16 AI router at `backend/app/compliance/routers/ai.py`. Permission `NOTICE_DRAFT_RESPONSE` (legal_team, ca_consultant, staff). Rate limit 12/minute matching Phase 17 extract-preview. Tenant scoping enforced via `_require_notice` defense-in-depth helper. Maps service exceptions to the standard 412/422/5xx Phase 16 error shape.

### 4. End-to-end smoke - `scripts/smoke_phase18_v20.py`

10 checks covering the full Phase 18 contract: service imports, endpoint registration, permission grants (3 yes legal/ca/staff, 4 no compliance_head/auditor/cfo/finance), BYOK 412 path before credential exists, real provider call (assert markdown body present with `Subject:` header and the notice_number embedded), audit redaction (no raw draft body or guidance text in audit details, body_sha256 + guidance_sha256 present), guidance round-trip (different guidance -> different sha256), audit immutability (UPDATE and DELETE both raise the append-only exception), RLS isolation (client B session cannot see client A's notice), and idempotent cleanup.

Verified 10/10 PASS against `gemini-2.5-flash-lite`: 1913-char draft body, 5879ms latency, 11 extracted fields used as context. CI-safe SKIP path verified separately.

## Verification

### Smoke output (live Gemini, 10/10 PASS)

```
[1/10] service_module_imports ... PASS
[2/10] endpoint_registered ... PASS
[3/10] permission_grants (3 yes, 4 no) ... PASS
[INFO] Fixture: user=63 client_a=325 client_b=326 notice=93
[4/10] byok_412_no_credential ... PASS
[INFO] AICredential id=16 provider=google model=gemini-2.5-flash-lite
[5/10] drafter_real_call (1913 chars, 5879ms) ... PASS
[6/10] audit_redaction (id=909) ... PASS
[7/10] guidance_round_trip (different guidance -> different sha256) ... PASS
[8/10] audit_immutability (UPDATE + DELETE both raised) ... PASS
[9/10] rls_isolation (client_b cannot see client_a notice) ... PASS
[10/10] cleanup_idempotent (audit rows retained per immutability) ... PASS

=== SMOKE PASSED ===
  Provider: google:gemini-2.5-flash-lite  tokens_out=1913  latency_ms=5879  extracted_fields_used=11
```

### Other gates

- `ruff check /app --select E,F,W --ignore E501`: clean.
- All 42 Phase 17 tests still pass; Phase 18 inherits the same pattern.
- OpenAPI exposes `/api/compliance/ai/notice-response-draft/{notice_id}` POST after backend reload.

## Deviations from CONTEXT

None of material consequence. The endpoint was added to the Phase 16 AI router (`routers/ai.py`) rather than to the response router (`routers/responses.py`) because all other BYOK AI surfaces live in `routers/ai.py` and grouping them keeps the rate-limit decorator, error mapper, and credential helper in one file.

## Known follow-ups (v2.1)

- Frontend integration of the AI-draft button in the response editor at `frontend/src/app/dashboard/compliance/notices/[id]/response/`.
- Persist-in-one-roundtrip variant: `POST /api/compliance/notices/{id}/responses/ai-draft` that drafts and creates a `notice_response_versions` row in a single call.
- Active-learning loop using the diff between draft body and eventually-submitted body as a tuning signal.
- Multi-variant fan-out (generate 3 candidate drafts, user picks one).
- Per-client_id rate-limit key once the broader rate-limiter refactor lands.

## Files written

- `backend/app/compliance/services/response_drafter_service.py` (new)
- `backend/app/compliance/services/response_drafter_prompt.py` (new)
- `backend/app/compliance/routers/ai.py` (modified: added `notice_response_draft` endpoint)
- `scripts/smoke_phase18_v20.py` (new)
- `.planning/phases/18-ai-response-drafting/18-CONTEXT.md` (new)
- `.planning/phases/18-ai-response-drafting/18-01-SUMMARY.md` (new, this file)
