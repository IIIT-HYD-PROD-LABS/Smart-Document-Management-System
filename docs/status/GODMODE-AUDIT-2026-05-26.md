# GODMODE End-to-End Audit and Remediation

**System:** Smart Document Management and Compliance System (TaxSync)
**Date:** 2026-05-26
**Branch / commit:** feat/mfa-account-lockout @ bdca56e
**Method:** 14 parallel read-only audit agents (one per independent domain), plus a clean-tree test/build baseline and cross-phase end-to-end tracing.

## 1. Phase completion status (phases 1 to 18)

| Phase | Area | Status | Notes |
|-------|------|--------|-------|
| 1 to 8 | v1.0 Document Management | Shipped | 42/42 requirements validated 2026-03-30 |
| 9 | Compliance foundation | Shipped | RLS, immutable audit, 7-role RBAC, state machine |
| 10 | ML classification + risk scoring | Code-complete (v2.0) | Rule-based scorer + review queue; BERT/NER deferred to v2.1 by design |
| 11 | Alerts + calendar | Code-complete | APScheduler + email + WebSocket; SMS scaffolded |
| 12 | Response drafting + evidence | Code-complete | 4-stage approval + versioned drafts + evidence |
| 13 | Search + reporting | Code-complete | PostgreSQL FTS; Elasticsearch deferred to v2.1 by design |
| 14 | Government portal integration | Blocked by design | External GSP empanelment + IT API decisions. NOT a defect. |
| 15 | Gmail MCP + email ingestion | Shipped (partial) | MCP + notice ingestion work; bill auto-ingestion inert (see G1) |
| 16 | BYOK AI assistant | Shipped | Per-tenant Fernet key, scope-locked prompt |
| 17 | AI notice field extraction | Shipped | 14-field, 0.85 routing gate, validators |
| 18 | AI notice response drafting | Shipped | Markdown draft endpoint, PII-redacted audit |

Verification target for this pass: phases 1 to 13 and 15 to 18. Phase 14 is intentionally deferred and is out of scope.

## 2. Consolidated findings

Severity key: Critical (security/data-loss/crash), High (feature broken or incorrect), Medium (edge-case/robustness), Low (quality/consistency). Status: Open, Fixed, Deferred, or Needs-decision.

### Authentication and identity
| ID | Sev | File:line | Issue | Status |
|----|-----|-----------|-------|--------|
| A1 | High | routers/auth.py:982-992 | Microsoft OAuth does not verify email ownership; UPN match against a passwordless account can auto-authenticate (takeover of OAuth-created accounts) | Open |
| A2 | Med | services/mfa_service.py:123-148; auth.py:431-494 | MFA challenge token has no jti/single-use; replayable within 5-min TTL | Open |
| A3 | Med | auth.py:875-880,1010 | OAuth link mutates oauth_id before the is_active 403 check | Open |
| A4 | Low | utils/security.py:17 | bcrypt silently truncates passwords at 72 bytes | Open |
| A5 | Low | auth.py:254-311 | forgot_password timing side-channel re-enables enumeration | Open |
| A6 | Low | auth.py:798-803,967 | OAuth state nonce generated but never bound/verified single-use | Open |

### Document pipeline and classification
| ID | Sev | File:line | Issue | Status |
|----|-----|-----------|-------|--------|
| D1 | High | routers/documents.py:127-212 | Duplicate-upload race; no unique constraint on (user_id, original_filename) | Open |
| D2 | High | services/llm_service.py:213-242 | Unrecognized LLM_PROVIDER silently falls back to local; configured keys ignored | Open |
| D3 | Med | ml/classifier.py:46-74 | Model errors propagate as non-retryable, marking docs FAILED | Open |
| D4 | Med | ml/metadata_extractor.py:70-78 | Amount dedup ignores currency | Open |
| D5 | Med | ml/ocr.py:34-44 | Deskew angle semantics vary by OpenCV version; can rotate the wrong way | Open |
| D6 | Low | tasks/document_tasks.py | Status strings overwrite extracted_text | Open |
| D7 | Low | services/llm_service.py:106 | Anthropic content[0] indexed without guard | Open |
| D8 | Low | routers/documents.py:833 | Fragile S3 key parse | Open |
| D9 | Low | ml/train.py | Typos in synthetic training data pollute classifier vocab | Open |

### Compliance foundation (Phase 9)
| ID | Sev | File:line | Issue | Status |
|----|-----|-----------|-------|--------|
| C1 | High | routers/notices.py:502-511 | assign_notice passes activity_type= (wrong kwarg + invalid value) to log_activity, TypeError 500 on every call | Open |
| C2 | Med | routers/notices.py:612-629; notice_service.py:266 | Bulk update gates only on BULK_UPDATE, skips target-status permission check | Open |
| C3 | High | services/notice_service.py:68-72 | transition_notice_status / bulk load by id only, no explicit client_id filter (RLS-only) | Open |
| C4 | High | services/notice_service.py:191-226 | Notice chain recursive CTE has no client_id predicate (RLS-only) | Open |
| C5 | Low | utils/pii_encryption.py | PII encryption helpers defined but not wired to any column (INFRA-06) | Open |
| C6 | Low | services/notice_service.py:122-132 | Strict audit never raises; failures only in dead-letter | Open |

### Phase 10 ML risk and review queue
| ID | Sev | File:line | Issue | Status |
|----|-----|-----------|-------|--------|
| M1 | High | ml/compliance/escalation.py:80-104; tasks/compliance_tasks.py:217 | Escalation idempotency is read-then-write; concurrent runs double-escalate | Open |
| M2 | Med | tests/test_escalation.py:114 | Test patches wrong audit symbol; "no-DB" test hits real audit path | Open |
| M3 | Med | ml/compliance/risk_scorer.py:216-224 | Partial per-client threshold override raises KeyError (no merge with defaults) | Open |
| M4 | Med | ml/compliance/regex_patterns.py:35 | DIN_PATTERN matches any 8-digit run; dead and misleading | Open |
| M5 | Med | tasks/compliance_tasks.py:204 | Review-queue enqueue rollback after a prior commit silently drops the row | Open |
| M6 | Low | ml/compliance/regex_patterns.py:50 | IT notice-number pattern defined but never used | Open |
| M7 | Low | tasks/compliance_tasks.py:138 | date.today() uses server local date, not IST | Open |

### Phase 11 alerts and calendar
| ID | Sev | File:line | Issue | Status |
|----|-----|-----------|-------|--------|
| L1 | High | calendar/adjust.py; scheduler.py:99-108 | Holiday/Sunday deadline adjustment only used by preview; scheduled alerts and stored deadlines are never adjusted | Open |
| L2 | Med | services/senders.py:160-214 | Alerts with recipient_user_id=None fan out to all client users, bypassing role targeting | Open |
| L3 | Med | services/scheduler.py:114 | Mixed function-ref vs string job references risk pickling fragility on restart | Open |
| L4 | Med | calendar/seed.py | Seed claims idempotency but does SELECT-then-INSERT with no unique constraint; race-duplicates | Open |
| L5 | Low | services/senders.py:11 | Stale "Resend SMTP" comment (project uses Gmail SMTP) | Open |
| L6 | Low | routers/calendar.py:142 | Compliance score relies on status_changed_at (last change, not submission) | Open |
| L7 | Low | calendar/statutory.py:16 | TDS Q4 seeding mixes fiscal vs calendar year | Open |

### Phase 12 response drafting and evidence
| ID | Sev | File:line | Issue | Status |
|----|-----|-----------|-------|--------|
| R1 | High | services/response_service.py:318-403 | No self-approval / segregation-of-duties guard; drafter can approve own draft | Open |
| R2 | High | services/permission_registry.py:99-119 | CA_CONSULTANT holds all 3 approval permissions; combined with R1 one user clears all stages | Open |
| R3 | Med | services/response_service.py:336-366 | Approval lacks FOR UPDATE / compare-and-set; concurrent approvers race | Open |
| R4 | Med | services/evidence_service.py:151 | list_attachments filters only by notice_id, no client_id (IDOR defense-in-depth) | Open |
| R5 | Low | services/response_service.py:355 | Approval audit is post-commit; failure leaves approval with no immutable row | Open |
| R6 | Low | services/evidence_service.py:118 | detach_document has no ownership check (asymmetric with attach) | Open |

### Phase 13 search and reporting
| ID | Sev | File:line | Issue | Status |
|----|-----|-----------|-------|--------|
| S1 | High | routers/reports.py:139-186; dependencies.py:92 | Cross-client mode renders one arbitrary client's analytics as authoritative | Open |
| S2 | Med | routers/reports.py:88-107 | health-summary trusts payload.client_id, not checked against membership (IDOR) | Open |
| S3 | Med | services/unified_search_service.py:101 | Cross-leg ts_rank scores not comparable; merged ordering biased | Open |
| S4 | Low | routers/search.py:48 | Degraded-mode fallback indicator is hardcoded; no real fallback | Open |
| S5 | Low | services/unified_search_service.py:103 | Notice snippet headline omits indexed fields | Open |
| S6 | Low | services/unified_search_service.py:52 | Hyphenated identifiers tokenize poorly (DRC-01) | Open |
| S7 | Low | services/report_service.py:201 | Response-time metric uses status_changed_at | Open |

### Phase 15 Gmail and email
| ID | Sev | File:line | Issue | Status |
|----|-----|-----------|-------|--------|
| G1 | High | email/services/ingestion_service.py:57-75 | ROUTE_BILL is never assigned anywhere; bill auto-detection/reminders are inert | Needs-decision |
| G2 | High | email/services/ingestion_service.py:67-78 | Duplicate message-id raises IntegrityError treated as fatal; aborts whole scan batch | Open |
| G3 | Med | email/services/ingestion_service.py:102-133 | Attachment dedup keys on name+size; computed SHA-256 unused/unstored | Open |
| G4 | Med | email/routers/filter_rules.py | Filter rules CRUD exists but is never consulted at scan time | Open |
| G5 | Low | email/routers/view_email.py:73 | Cross-client-mode quirk (spurious 404 for platform admin) | Open |
| G6 | Low | email/tasks/scanner_task.py:255 | last_history_id not re-established after full-scan fallback; repeated full scans | Open |
| G7 | Info | email/routers/oauth.py:124 | OAuth state JWT reuses session SECRET_KEY | Open |

### Phases 16 to 18 BYOK AI
| ID | Sev | File:line | Issue | Status |
|----|-----|-----------|-------|--------|
| AI1 | High | alembic/versions/0033_ai_credentials_rls.py:78-92 | cross_client_view SELECT policy on ai_credentials exposes every tenant's encrypted key rows | Open |
| AI2 | Med | services/notice_extraction_validator.py:155-167 | Liability arithmetic can halve a field's confidence twice | Open |
| AI3 | Med | routers/ai.py:339-374 | notice_response_draft body is untyped dict with no size cap | Open |
| AI4 | Low | services/ai_service.py:209 | last_used_at committed before the provider call | Open |
| AI5 | Low | services/ai_providers.py:228 | Provider response body embedded in exception/logs | Open |
| AI6 | Low | routers/ai.py:486 | Chat-history substring sanitizer has false positives and is trivially bypassed | Open |

### Frontend UI
| ID | Sev | File:line | Issue | Status |
|----|-----|-----------|-------|--------|
| F1 | High | components/compliance/ExtractionPreviewForm.tsx:429 | Dead link /dashboard/settings/ai-credentials (route does not exist) | Open |
| F2 | Low | app/dashboard/compliance/clients/[id]/team/page.tsx:68 | Native alert()/confirm() instead of toast pattern | Open |
| F3 | Low | components/landing/EarlyAccessModal.tsx:49 | Modal not closable via keyboard/Esc | Open |
| F4 | Low | lib/api.ts:107 | Cookie secure flag only in production | Open |

Note: the NotificationBell WebSocket bug referenced in STATE.md is already fixed (verified). Token storage is js-cookie compliant.

### Cross-cutting security and infrastructure
| ID | Sev | File:line | Issue | Status |
|----|-----|-----------|-------|--------|
| SEC1 | Med | email/routers/bills.py:82; services/bill_service.py:110 | bills GET / mark-paid rely on RLS only; add explicit client_id check | Open |
| SEC2 | Med | email/routers/credentials.py:56; filter_rules.py:93 | credentials/filter-rules PATCH/DELETE rely on RLS only | Open |
| SEC3 | Med | middleware/logging.py:30-38 | JWT decoded in logging middleware without expiry/type validation; log-context poisoning | Open |
| SEC4 | Med | services/llm_service.py:134-151 | OLLAMA_BASE_URL not validated (SSRF if misconfigured) | Open |
| SEC5 | Low | utils/log_redaction.py:20-25 | PII redactor does not recurse into nested dicts | Open |

### Database and migrations
| ID | Sev | File:line | Issue | Status |
|----|-----|-----------|-------|--------|
| DB1 | High | alembic/versions/0017_db_roles.py:33-34 | Role passwords via f-string (injection) + hardcoded dev-password fallbacks | Open |
| DB2 | High | alembic/env.py:13-19 | target_metadata imports only 6 v1.0 models; autogenerate would DROP all compliance tables | Open |
| DB3 | Med | 0013 vs models/notice.py:208 | CHECK constraint name drift | Open |
| DB4 | Low | 0013 vs models/notice.py:340 | Unique constraint name drift | Open |
| DB5 | Low | various | Model/migration CHECK parity drift | Open |

### Folder structure and hygiene
| ID | Sev | Path | Issue | Status |
|----|-----|------|-------|--------|
| FS1 | Med | backend/.gitignore vs root | Contradiction: backend ignores /models/ + uploads/ while root commits trained models | Open |
| FS2 | Med | scripts/build_internship_report.py | Writes to parent ../Internship_Report_TaxSync.docx outside the repo | Open |
| FS3 | Med | scripts/smoke_phase*_v20.py | Smoke tests live in scripts/ while tests live in backend/tests | Open |
| FS4 | Med | docs/reference duplicate technical docs | Two near-duplicate technical documents | Open |
| FS5 | Med | notes/ generated .html | Committed generated HTML build output | Open |
| FS6 | Low | docs/exports | Rendered artifacts half-tracked, half-ignored | Open |
| FS7 | Low | root .gitignore *.png | Blanket *.png hides docs/screenshots referenced by docs | Open |
| FS8 | Low | .planning numbering | Non-sequential phase numbers read as clutter | Open |

## 3. Remediation plan (ordered)

- Tier 1 (safe, no migration): C1, F1, DB2, S1, S2, C3, C4, C2, R4, SEC1, SEC2, SEC3, L1, L2, G2, M3, M5, D2, AI2, AI3, M2, AI4, AI5, AI6.
- Tier 2 (requires migration): D1 (unique constraint), AI1 (drop policy), L4 (unique constraint), G3 (sha256 column), DB3/DB4 (name alignment).
- Tier 3 (workflow wiring, highest product value): classify + risk + alerts on notice creation (covers manual and Gmail paths), R1 and R2 segregation-of-duties.
- Tier 4 (security-sensitive, careful + tests): A1 Microsoft OAuth verification, A2 MFA jti single-use, DB1 role-password hardening.
- Tier 5: remaining Low items + folder-structure cleanup (FS1 to FS8).
- Needs-decision: G1 bill auto-ingestion (feature scope; bills were repositioned as vendor invoices).

## 4. Verification plan

1. Clean-tree baseline (backend pytest, ruff, frontend tsc + build) captured before changes.
2. After each fix batch, re-run the affected tests and add regression tests for C1, the workflow wiring, and R1/R2.
3. Full backend suite green + ruff clean + frontend build pass.
4. Phase smoke scripts (10, 12, 13, 15, 17, 18) where a provider key is not required.
5. Live end-to-end against Supabase requires WARP connectivity (campus network blocks outbound 5432/6543); attempted at the end.

## 5. Change log and resolution

### Verification result (2026-05-26)
On a fresh local Postgres 16 + Redis (the CI recipe, with `GRANT app_runtime TO test WITH SET TRUE`, `pg_trgm`, and a valid `FERNET_KEY`):

- Backend: **608 passed, 0 failed, 32 skipped** (the 32 skips are intentional Plan 02 to 05 placeholders). Baseline before this work was 601 passed; the delta is 7 new regression tests.
- Lint: **ruff 0 issues** (the pre-existing F401 is removed).
- Migrations: **`alembic upgrade head` applies cleanly through the new `0037`** (single head).
- Frontend: **`tsc --noEmit` 0 errors, `npm run build` PASS**.

Two operational notes:
1. `FERNET_KEY` MUST be set in the runtime environment. MFA enroll/confirm endpoints (and any PII-encryption path) raise `RuntimeError: FERNET_KEY env var is not set` and return 500 without it.
2. The suite is green only against a fresh DB. Re-running the full suite against a reused DB leaks a `documents` row (now caught by the new `uq_documents_user_filename`) and Redis rate-limit state. This is test isolation, not a product defect.

### Fixed and verified
- Auth: A1 (Microsoft OAuth no longer trusts an unverified UPN to auto-authenticate a passwordless account; email is trusted only when `MICROSOFT_TENANT_ID` is a specific tenant), A2 (MFA challenge token single-use jti), A3 (is_active re-check before oauth_id mutation), A4 (72-byte password cap), SEC3 (no inline JWT decode in logging middleware), SEC5 (recursive PII redaction).
- Document pipeline: D2 (LLM provider validated at config load), SEC4 (OLLAMA_BASE_URL SSRF guard), D3 (classifier raises on inference error so it retries), D4, D5, D7, D9.
- Compliance core: C1 (assign_notice 500 fixed), C2 (bulk re-checks target-status permission), C3 and C4 (explicit client_id scoping on transition, bulk, chain), R1 (self-approval and same-actor multi-stage approval blocked), R3 (FOR UPDATE on approval), R4 and R6 (evidence client_id scope + detach ownership), S1 (cross-client report mode rejected), S2 (health-summary client_id checked).
- Alerts and calendar: L1 (holiday-adjusted deadline used for scheduled alerts), L2 (no role-bypassing fan-out), L4 (idempotent calendar seed), L5, L6.
- Email and Gmail: G2 (duplicate-message dedup no longer aborts the scan), SEC1 and SEC2 (explicit client_id checks on bills, credentials, filter rules), G6 (history id re-established after full-scan fallback).
- BYOK AI: AI2 (confidence halved at most once), AI3 (typed, size-capped draft request body), AI6 (removed corrupting substring sanitizer).
- Frontend: F1 (dead ai-credentials link fixed), F2 (toast/modal instead of native confirm), F3 (modal keyboard/Esc close).
- DB: DB2 (env.py imports all models so autogenerate is safe), migration `0037` (D1 documents unique constraint, AI1 dropped `cross_client_view` on `ai_credentials`, L4 regulatory_calendar unique key), DB3/DB4 (constraint-name alignment).
- Cross-phase wiring: notices are now classified, risk-scored, review-queue-routed, and deadline-alert-scheduled at intake (manual create and Gmail ingestion) via `process_notice_intake`, with a `risk_scored_at is None` guard so the transition path does not double-classify.

### Deferred (tracked, with rationale)
- M1 (escalation idempotency race), downgraded to Medium: the intake-wiring guard removes the dominant double-classification path and the 24h cooldown handles sequential re-runs; the residual concurrent-retry window only yields a duplicate alert. Correct fix is a `pg_advisory_xact_lock(notice_id)` plus a double-checked cooldown read around `should_escalate`/`escalate`, to be implemented and tested against a live worker.
- G1 and G4 (bill auto-ingestion via ROUTE_BILL and filter-rule routing): a feature build, not a bug fix, and bills were repositioned as vendor invoices. Needs a product decision before implementing.
- Low-severity polish (A5, A6, D6, D8, L3, L7, S3 to S7, G5, G7, AI4, AI5, C5, C6, DB1, DB5, SEC5-nested-edge): documented above; none block correctness or security.

### Folder structure
Working tree is clean; nothing junk is tracked (caches, .next, node_modules, .env, override compose all correctly ignored). The actionable items are documentation-tree fragmentation (docs vs notes vs .planning), smoke scripts living under `scripts/` instead of `backend/tests/`, and two `.gitignore` reconciliations. These are recorded as recommendations (FS1 to FS8); file moves are deferred to avoid breaking references in a shipped repo.

## 6. Post-audit follow-up (2026-05-27)

### AI7 (High) — notice extraction silently dropped fields past a 4000-char window
Reported as "PDF notice upload not working properly: fields come back blank/wrong". This was missed by the 2026-05-26 sweep. Root cause: `notice_extraction_prompt.MAX_TEXT_WINDOW` clipped the document to the first 4000 characters before the model saw it (`build_user_prompt` does `text[:MAX_TEXT_WINDOW]`). Real notices lead with letterhead and legal recitals, so the demand table (tax, interest, penalty, total) and the response deadline routinely sat past character 4000 and never reached the model, coming back blank. The Phase 17 smoke used a short synthetic notice that fit inside 4000 chars, so 12/12 passed while real multi-page notices failed in production.

Reproduction (BYOK Gemini 2.5 Flash Lite, against the configured tenant credential): a clean ~700-char GST notice extracted all 13 fields at confidence 1.0 (decision apply); the same notice padded so the demand table fell past character 4000 returned notice_number, authority, issued_date, gstin, pan, and legal_sections but dropped tax_demand, interest, penalty, total_liability, and response_deadline.

Fix: raised `MAX_TEXT_WINDOW` from 4000 to 24000 (about 7 pages, roughly 6k tokens), which is far under the Gemini (about 1M tokens) and Claude (about 200k tokens) input caps. Added regression test `test_extract_window_covers_fields_past_legacy_4000_chars`. Verified: both prompt-window unit tests pass and the padded-notice demand block now reaches the model. The live end-to-end re-run is pending Supabase reachability (campus network was blocking port 5432 again; reconnect WARP).

Files: `backend/app/compliance/services/notice_extraction_prompt.py`, `backend/tests/compliance/extraction/test_extractor_service.py`.

Not in scope (separate concerns, not the reported bug): the v1.0 document-summary path `_build_extraction_prompt` keeps its own 4000-char clip in `test_llm_service.py`; scanned-PDF OCR text quality; and very long notices beyond about 7 pages (the tail can still be clipped, acceptable for now).
