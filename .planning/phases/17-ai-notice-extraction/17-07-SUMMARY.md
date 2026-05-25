# Plan 17-07 Summary: Wave 6 End-to-End Smoke + Docs Roll-Up

**Status:** SHIPPED 2026-05-25
**Phase:** 17 (AI Notice Field Extraction, Zero-Shot, BYOK)
**Wave:** 6
**Result:** Phase 17 v2.0 ships. Smoke 12 of 12 PASS.

## Delivered

### 1. End-to-end smoke — `scripts/smoke_phase17_v20.py`

558 lines. Twelve checks, fail-fast on the cheap infrastructure ones, fail-soft on the four checks that depend on the live provider so the audit, immutability, and RLS contracts still get verified when the provider call fails. CI safe: when neither `ANTHROPIC_API_KEY_SMOKE` nor `GEMINI_API_KEY_SMOKE` is set, the smoke prints a single `SKIPPED` line and exits 0.

The 12 checks:

1. `alembic_head` confirms migration `0034_phase17_notice_extraction` is applied.
2. `columns_present` confirms the 5 extraction columns plus the 2 CHECK constraints (status enum, confidence range).
3. `permission_registered` confirms `NOTICE_AI_EXTRACT` is granted to compliance_head, ca_consultant, staff and is NOT granted to legal_team, auditor, cfo, finance_team.
4. `byok_412_no_credential` confirms `extract_notice_fields` raises `NoticeExtractionCredentialMissingError` when the tenant has no `AICredential` row (the seed of the HTTP 412 path).
5. `extract_real_call` runs the live provider call against `tests/compliance/extraction/fixtures/gst_drc_01_sample.txt` and asserts the envelope contains all four critical fields: notice_number, authority, issued_date, response_deadline.
6. `routing_gate_apply` confirms `route_or_apply` returns `action='apply'` when the conjunctive 0.85 gate clears.
7. `persist_envelope` confirms `apply_extraction_to_notice` writes all five columns and flips `extraction_status` to `completed`.
8. `audit_redaction` confirms exactly one `notice_ai_extract` row landed with the expected key set, the body SHA-256 matches the host-recomputed hash of the fixture text, and the row contains NEITHER raw text NOR any extracted field value. This check fires even when the provider call fails, because the extractor's failure path also writes an audit row.
9. `accept_audit_per_field` accepts the 4 critical fields via `log_audit_event` and asserts one `notice_ai_extract_accepted` row per field, each with `original_value_sha256`, `accepted_value_sha256`, and `was_edited=false`. Raw values are absent from the serialised details.
10. `audit_immutability` proves UPDATE and DELETE on the audit row both raise the `audit_logs is append-only` exception from migration 0014 (Phase 9 inheritance).
11. `rls_isolation` opens a second engine bound to `DATABASE_URL_RUNTIME` (the `app_runtime` role), sets the tenant context to client B via `set_config(...)`, and asserts that a query for client A's notice row returns zero rows.
12. `cleanup_idempotent` deletes the fixture rows in reverse dependency order; audit rows survive (immutability proved them safe to retain).

### 2. README.md addition

New section under "Features":

- v2.0 Phase 15 entry (was missing in main README; added retroactively as part of this roll-up).
- v2.0 Phase 17 entry covering upload-first creation, the conjunctive routing gate, the PII-redacted audit chain, the provenance disclosure, wiring parity across the three ingestion paths (extract-preview, Celery, Gmail), and the smoke invocation.
- Phases table extended with Phase 15, 16, 17 rows.

### 3. ROADMAP.md updates

- Phase 17 entry in the v2.0 list (with EXTRACT-01..12 mapped to the 9 success criteria) and 7 plans checked off.
- Phase 17 row in the Progress table.
- "Last updated" footer rewritten with the 12/12 smoke result, Gemini metrics, and v2.1 deferrals enumerated.

### 4. STATE.md updates

- `stopped_at` moved to Phase 17 v2.0 shipped.
- `last_updated` set to 2026-05-25.
- Progress counters: 7 of 9 phases complete (up from 4 of 7), 33 of 33 plans complete.
- "Current Position" rewritten to point at Phase 17 plan 07 shipped, next phase 14 (still blocked).
- "Shipped Milestones" gained Phase 15, Phase 16, Phase 17 bullets.
- "Session Continuity" updated with the new last-session entry.

### 5. 17-07-PLAN.md authored

Filled the gap in the Phase 17 plan series. The plan describes the smoke contract per D-32, the README / ROADMAP / STATE deliverables, the verification gate, and the decision deltas allowed under "Claude's discretion".

### 6. 17-07-SUMMARY.md (this file)

## Verification

### Smoke output (full path, 12 of 12 PASS)

```
[INFO] Fixture loaded from /app/tests/compliance/extraction/fixtures/gst_drc_01_sample.txt
[1/12] alembic_head (0034_phase17_notice_extraction) ... PASS
[2/12] columns_present (5 cols + 2 CHECK constraints) ... PASS
[3/12] permission_registered (3 grants, 4 negatives) ... PASS
[INFO] Fixture: user=63 client_a=272 client_b=273
[4/12] byok_412_no_credential (D-14) ... PASS
[INFO] AICredential id=8 provider=google model=gemini-2.5-flash-lite
[5/12] extract_real_call (avg=0.99, fields=13) ... PASS
[6/12] routing_gate_apply (avg≥0.85, critical fields cleared) ... PASS
[7/12] persist_envelope (5 cols + extraction_status=completed) ... PASS
[8/12] audit_redaction (id=807, keys-only, body_sha256 ok) ... PASS
[9/12] accept_audit_per_field (4 rows, hashed values) ... PASS
[10/12] audit_immutability (UPDATE + DELETE both raised) ... PASS
[11/12] rls_isolation (client_b cannot see client_a notice) ... PASS
[12/12] cleanup_idempotent (notices/memberships/creds/clients dropped; audit rows retained per immutability) ... PASS

=== SMOKE PASSED ===
  Provider: google:gemini-2.5-flash-lite  avg_confidence=0.99  latency_ms=3568  fields=13
```

Run command (the one used):

```
docker cp scripts/smoke_phase17_v20.py smartdocs-backend:/tmp/
docker exec -e GEMINI_API_KEY_SMOKE=$KEY \
  -e GEMINI_MODEL_SMOKE=gemini-2.5-flash-lite \
  smartdocs-backend python /tmp/smoke_phase17_v20.py
```

### Skip-path verification

```
docker exec smartdocs-backend env -u ANTHROPIC_API_KEY_SMOKE python /tmp/smoke_phase17_v20.py
SKIPPED: Neither ANTHROPIC_API_KEY_SMOKE nor GEMINI_API_KEY_SMOKE set; ...
EXIT=0
```

CI safety contract holds.

## Deviations from the plan

### D-1: Gemini fallback added to the smoke

Plan 17-CONTEXT D-32 specifies a "real Anthropic Sonnet call". The smoke was written Anthropic-first, but when the user did not have a working Anthropic key in this session and the only available live provider was Gemini, the smoke gained a fallback that picks `GEMINI_API_KEY_SMOKE` when `ANTHROPIC_API_KEY_SMOKE` is not set. The contract on what the smoke verifies is unchanged — same 12 checks, same audit shape, same routing gate, same persistence. The only thing that differs is which provider produced the envelope. Anthropic is still preferred whenever its key is present, matching D-32's intent.

### D-2: Smoke runs via docker cp + docker exec, not as a bind-mounted script

The host project has `scripts/` at the project root, but the backend container only mounts `./backend:/app`. The earlier phase smokes (Phase 15) assume `/app/../scripts/` resolves, which it doesn't. The 17 smoke handles this two ways: (a) it walks a candidate list for the fixture path, picking the first existing file across host and container layouts; (b) the documented invocation does `docker cp` then `docker exec`, which is the only path that actually worked. A future tooling plan could add `./scripts:/scripts` to the compose file and drop the docker-cp step.

### D-3: `ClientMembership.compliance_role` vs `role`

First smoke run failed instantiating `ClientMembership` with `role=...`. The model column is `compliance_role`. Fixed inline.

### D-4: First live-call key was expired, second was rate-limited, third worked

The container's `GEMINI_API_KEY` env returned `API_KEY_INVALID` (key expired). The user-supplied replacement returned HTTP 429 (quota exceeded) on `gemini-2.0-flash`. Switching to `gemini-2.5-flash-lite` via `GEMINI_MODEL_SMOKE` cleared the quota and the smoke completed. This validates that the smoke surfaces real upstream failures correctly rather than swallowing them.

## Notable findings (not blocking ship)

- **Container's `GEMINI_API_KEY` env var is expired.** The dev/staging Gemini key inside `smartdocs-backend` returns `API_KEY_INVALID`. Worth refreshing before any future live-call smoke is run against this default; the smoke does not depend on it (the BYOK key is per-tenant), but local manual testing of the AI features will fail until rotated.
- **Phase 17 audit redaction holds on the failure path too.** Check 8 passed even on the runs where the provider call failed, because `notice_extractor_service._write_audit` writes the redacted row before re-raising. This is the right shape; worth keeping if anyone refactors the failure path.
- **`gemini-2.0-flash` quota is tight on the free tier.** Use `gemini-2.5-flash-lite` for development-time smokes; reserve `gemini-2.0-flash` (or Anthropic Sonnet) for production tenants whose keys carry paid-tier quota.

## Known follow-ups (queued as v2.1 in ROADMAP)

- Vitest install + bodies for the 14 `it.todo` cases in the 3 extraction frontend stubs (deferred from Plan 17-06 per the Phase 15 precedent of "vitest install is a future tooling plan").
- Authenticated browser walk of the upload-first flow on `/dashboard/compliance/notices/new` (Plan 17-06 explicitly owed; the smoke covers service-layer behaviour, not the click-path).
- Supervised NER / BERT bake-off (Phase 10 v2.1) remains deferred; the extractor service interface lets a future plan swap the zero-shot LLM path for a supervised model without touching the routing, audit, or persistence code.
- Tabular line-item extraction (annexure tables).
- Bulk re-extraction of historical notices.
- Cross-validation of extracted GSTIN / PAN against authoritative registries.
- Active-learning loop where corrected fields become training data.

## Files written

- `scripts/smoke_phase17_v20.py` (new)
- `.planning/phases/17-ai-notice-extraction/17-07-PLAN.md` (new)
- `.planning/phases/17-ai-notice-extraction/17-07-SUMMARY.md` (new, this file)
- `README.md` (Phase 15, 16, 17 sections + phase table rows)
- `.planning/ROADMAP.md` (Phase 17 entry + plan list + Progress table row + footer rewrite + Phase 16 backfill)
- `.planning/STATE.md` (header, Current Position, Shipped Milestones, Session Continuity)

## Out of scope (as planned)

- New service code or routes (anything code-changing would live in Plan 17-03 through 17-06).
- Frontend test bodies (vitest install is a future tooling plan).
- Bulk re-extraction.
- Cross-checking extracted GSTIN / PAN against authoritative registries.
- Performance benchmarking against a SLO target.
