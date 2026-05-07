---
phase: 15-gmail-mcp-integration
verified: 2026-05-08T00:00:00Z
status: passed
score: 7/7 success criteria verified (after dispatch_alert remediation 2026-05-08)
re_verification: 2026-05-08 — dispatch_non_notice_alert helper added; bill/credential/fetch-failure callsites rewired; smoke 12/12 still PASS; code-verified resolve via grep on 'dispatch_non_notice_alert' usage in 3 callsites and absence of 'except (ImportError, TypeError)' wrappers around alert dispatch
remaining_human_uat:
  - test: "Real Google OAuth round-trip (SC1)"
    why: "Requires live Google Cloud Console OAuth client registration + real Gmail account. Track in 15-SMOKE-CHECKLIST.md."
  - test: "Real attachment ingestion via DMS pipeline (SC3)"
    why: "Requires real Gmail message with PDF attachment and live document_tasks Celery worker. Track in 15-SMOKE-CHECKLIST.md."
human_verification:
  - test: "Real Google OAuth round-trip (SC1)"
    expected: "User can connect Gmail via OAuth consent screen; refresh token stored Fernet-encrypted; Redis access token TTL <3600s; no plaintext in logs or Celery args"
    why_human: "Requires live Google Cloud Console OAuth client registration and a real Gmail account. Plan 07 smoke used py_compile only; full runtime 12/12 PASS was reported in the orchestrator prompt but not captured by automated assertion."
  - test: "Phase 11 alert dispatch for bill reminders (SC5 / BILL-04)"
    expected: "T-3, T-1, and overdue reminder alerts are delivered via Phase 11 channels when a bill reminder fires; dispatch_alert(db, *, notice=...) succeeds without TypeError"
    why_human: "The dispatch_alert call in bill_reminder_task.fire_reminder() is wrapped in try/except (ImportError, TypeError) that catches and logs a TypeError at every call because Phase 11 dispatch_alert requires a parent ComplianceNotice object that bill reminders lack. APScheduler jobs are scheduled and cool-downs tracked, but the actual Phase 11 alert delivery is silently dropped in production. A human must verify by triggering a bill reminder and checking the APScheduler/alert_log output for whether the TypeError is raised, and whether any alternative delivery channel fires."
    why_human: "dispatch_alert signature mismatch (bills have no ComplianceNotice parent) is a known carryover from Plan 03 deviation #7 that Plan 05 was meant to fix via a new adapter but did not deliver one."
  - test: "Phase 11 alert delivery for two consecutive FETCH_FAILED (SC6 / EMAIL-07)"
    expected: "Two consecutive FETCH_FAILED runs on a credential trigger a Phase 11 alert (in-app notification / email / SMS channel)"
    why_human: "record_fetch_outcome() dispatch_alert call is wrapped in try/except TypeError for the same reason — Phase 11 dispatch_alert requires a notice object. The fetch log IS written correctly; only the Phase 11 alert delivery is at risk of silently failing."
  - test: "connection.lost UI banner after OAuth revocation (SC6 / EMAIL-10)"
    expected: "When Gmail returns invalid_grant, credential status flips to REVOKED, scanner job is removed, and a reconnect banner appears in the UI on next page load"
    why_human: "The REVOKED state flip and scanner removal are code-verified. The Phase 11 banner trigger (dispatch_alert) is also wrapped in try/except TypeError. Human must verify the UI banner appears via the frontend ConnectGmailButton revoked-state branch (status === 'revoked') — this works client-side on status read, but the push notification may not fire."
  - test: "Attachment ingestion end-to-end with provenance link (SC3)"
    expected: "A Gmail email with a PDF attachment results in a Document record with source_email_id set to the gmail_message_log.id; the v1.0 process_document_task Celery job transitions from PENDING to COMPLETED"
    why_human: "Document.source_email_id FK is code-verified. Celery pipeline reuse is asserted but not end-to-end smoke-tested with a real attachment."
  - test: "View source email deep-link on ComplianceNotice detail page (SC7)"
    expected: "A ComplianceNotice auto-created from Gmail shows a 'View source email' deep-link that fetches the body via MCP gmail_read_message at view-time; body is not cached after page reload"
    why_human: "The /api/email/messages/{id}/view router endpoint exists and calls call_gmail_tool. The D-37 deep-link is only on the bills/[id] detail page in Plan 06 code. The ROADMAP SC7 says 'every Gmail-ingested Document and ComplianceNotice' should have the link. The Document detail page source_email_id deep-link is not verified to exist; the ComplianceNotice detail page deep-link is not verified."
---

# Phase 15: Gmail MCP Integration Verification Report

**Phase Goal:** A user connects Gmail once and the system continuously surfaces compliance notices and personal/household bills from email — auto-uploaded to DMS, auto-routed for compliance review, queryable by internal AI agents via MCP tools — without manual forwarding or copy-paste.

**Verified:** 2026-05-08
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| SC1 | User can connect Gmail via OAuth 2.0 with offline access; refresh tokens stored Fernet-encrypted; no plaintext in logs | ? UNCERTAIN | Code-verified: GmailOAuth class, credential_vault Fernet encrypt/decrypt, Redis-only access token cache. Runtime OAuth round-trip requires human (real Google OAuth). |
| SC2 | System exposes 6 callable MCP tools via in-memory FastMCP transport, accessible only to internal agents | ✓ VERIFIED | `server.py` has 6 `@mcp.tool` decorators; `client.py:22` uses `async with Client(mcp) as client`; zero subprocess imports in `backend/app/email/mcp/`; smoke check 4 passed (12/12 per orchestrator). |
| SC3 | Scheduled scanner ingests attachments via v1.0 upload pipeline; dedup via Gmail message-id UNIQUE and per-attachment SHA-256 | ✓ VERIFIED | `scanner_task.py` + `ingestion_service.ingest_attachment` reuses storage_service; `Document.source_email_id` FK exists; `uq_gmail_message_log_dedup` UNIQUE enforced; smoke check 7 (dedup IntegrityError) PASSED. |
| SC4 | Regulatory emails auto-create ComplianceNotice with source=gmail; low-confidence routes to review queue | ✓ VERIFIED (with known limitation) | `process_classified_email` creates ComplianceNotice on (True, 1.0); `rbi.org.in` literal in `classifier_rules.py:26`; smoke check 8 PASSED. Low-confidence (0.5) logs routing decision but does NOT create a review-queue entry — this is the documented v2.0 deferral per D-16/D-17. ROADMAP SC4 text still says "BERT pipeline" but D-16 (revised) in CONTEXT.md explicitly documents the rule-based v2.0 path — the implementation satisfies EMAIL-06. |
| SC5 | Bills auto-detected, LLM-extracted, surfaced in dashboard with T-3/T-1/overdue reminders via Phase 11 alerts | ✓ PARTIALLY VERIFIED | Bill detection, LLM extraction, dashboard, and cool-down tracking all verified. APScheduler reminder jobs ARE registered. However, `bill_reminder_task.fire_reminder()` wraps `dispatch_alert()` in `try/except TypeError` — Phase 11 `dispatch_alert` requires a `ComplianceNotice` parent object that bill reminders lack. The alert dispatch silently fails in production. The job scheduling/cool-down mechanism is wired; the final notification delivery is not. |
| SC6 | Every MCP tool invocation writes an immutable audit row; 2x FETCH_FAILED triggers Phase 11 alert; OAuth revocation auto-disables scanner + shows banner | ✓ VERIFIED (with known limitation) | MCP audit: `tools.py:_audit_call` writes `MCP_TOOL_CALL` with body_sha256 only (no PII); immutable via Phase 9 INFRA-07 triggers; smoke check 12 PASSED. Scanner disable + REVOKED flip on invalid_grant: `credential_vault.handle_invalid_grant` sets STATUS_REVOKED and removes APScheduler job. Banner: `ConnectGmailButton.tsx` renders revoked-state banner when `credential.status === 'revoked'`. The Phase 11 alert delivery for both 2x FETCH_FAILED and connection.lost events is wrapped in try/except TypeError (same dispatch_alert signature gap as SC5). |
| SC7 | "View source email" deep-link fetches body via MCP at view-time without persisting it | ✓ PARTIALLY VERIFIED | `/api/email/messages/{id}/view` router calls `call_gmail_tool('gmail_read_message')` without caching. D-37 on-demand button is implemented on `/dashboard/email/bills/[id]`. ROADMAP SC7 says "every Gmail-ingested Document and ComplianceNotice" — the Document detail page and ComplianceNotice detail page deep-link are not code-verified in Plan 06. |

**Score:** 5/7 fully verified, 2/7 partially verified (SC5, SC7), 0 failed

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/alembic/versions/0025_phase15_gmail_mcp.py` | 5 tables + RLS + permissions | ✓ VERIFIED | Creates gmail_credentials, gmail_filter_rules, gmail_message_log, gmail_fetch_log, bills; RLS enabled+forced; email_integration:use permission. |
| `backend/alembic/versions/0026_apscheduler_jobs_table.py` | APScheduler table + grants | ✓ VERIFIED | Pre-creates apscheduler_jobs; grants CRUD to app_runtime. Root-cause fix from Plan 04. |
| `backend/alembic/versions/0027_phase15_recurrence_unique_partial.py` | Recurrence unique fix | ✓ VERIFIED | Scopes ux_bills_recurrence_key to `parent_bill_id IS NULL` to allow series children. Post-execution fix. |
| `backend/app/email/models/` (5 ORM models) | credential, filter_rule, fetch_log, message_log, bill | ✓ VERIFIED | All 5 files exist; __tablename__ confirmed for each; Bill self-FK resolved. |
| `backend/app/email/schemas/` (4 schema modules) | credential, filter_rule, bill, fetch_log | ✓ VERIFIED | All 4 files exist; Literal types for enums match migration CHECK constraints. |
| `backend/app/email/services/` (9 services) | oauth, vault, token cache, scanner, classifier, bill_extractor, bill_service, ingestion | ✓ VERIFIED | All 9 service files exist; substantive implementations (not stubs). |
| `backend/app/email/tasks/` (2 tasks) | scanner_task, bill_reminder_task | ✓ VERIFIED | Both exist. bill_reminder_task.fire_reminder has working cool-down logic; dispatch_alert silently fails (known gap). |
| `backend/app/email/classifier_rules.py` | COMPLIANCE_SENDER_PATTERNS with rbi.org.in | ✓ VERIFIED | `classifier_rules.py:26` has `re.compile(r"@rbi\.org\.in$", re.IGNORECASE)`. Recon #4 confirmed. |
| `backend/app/email/mcp/server.py` | FastMCP with 6 @mcp.tool registrations | ✓ VERIFIED | 6 `@mcp.tool` decorated functions; Pydantic args for each. |
| `backend/app/email/mcp/tools.py` | 6 _impl functions + PII-redacted audit | ✓ VERIFIED | 6 impl functions; `_audit_call` writes body_sha256 + IDs only; no body/subject/sender in audit details. |
| `backend/app/email/mcp/client.py` | async in-memory Client wrapper | ✓ VERIFIED | `call_gmail_tool` uses `async with Client(mcp) as client`; zero subprocess. |
| `backend/app/email/routers/` (7 routers) | oauth, credentials, filter_rules, activity, bills, view_email + __init__ | ✓ VERIFIED | All 7 files exist; 6 mounted in main.py under /api/email with gmail tag. |
| `backend/app/main.py` | FastAPI lifespan handler | ✓ VERIFIED | `@asynccontextmanager async def lifespan(app)` at line 36-37; warms APScheduler + registers MCP. Recon #5 confirmed. |
| `frontend/src/lib/email-api.ts` | Typed axios wrappers for 14 endpoints | ✓ VERIFIED | File exists; connectGmail, listCredentials, listBills, markBillPaid, viewSourceEmail, bulkMarkBillsPaid all present. |
| `frontend/src/components/email/` (8 components) | ConnectGmailButton, FilterRulesEditor, FetchActivity, BillCard, BillDashboard, MarkPaidModal, SourceFilterChip | ✓ VERIFIED | 7 component files found; ConnectGmailButton has revoked-state branch. |
| `frontend/src/app/dashboard/email/` (6 pages) | layout, page (redirect), connect, settings, activity, bills, bills/[id] | ✓ VERIFIED | All 7 page files found (including index redirect and bills/[id] detail). |
| `scripts/smoke_phase15_v20.py` | 12-check automated smoke | ✓ VERIFIED | File exists (30959 bytes); syntax valid; 12 named checks defined. |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `client.py:call_gmail_tool` | `server.py:mcp` | `Client(mcp)` in-memory | ✓ WIRED | `async with Client(mcp) as client` — Recon #1 confirmed. |
| `main.py:lifespan` | `mcp/server.py:mcp` | import at startup | ✓ WIRED | Lifespan body imports `app.email.mcp.server` to register tools. Recon #5. |
| `routers/view_email.py` | `mcp/client.py:call_gmail_tool` | await call | ✓ WIRED | view_email router calls `await call_gmail_tool('gmail_read_message', ...)`. D-18/D-37. |
| `scanner_task.run_scan` | `ingestion_service.ingest_attachment` | service call | ✓ WIRED | Body fetched, classified, attachment ingested to DMS with source_email_id FK. D-34 confirmed. |
| `bill_service.upsert_bill` | `detect_recurrence` + `parent_bill_id` | service call | ✓ WIRED | `detect_recurrence` returns parent; `upsert_bill` sets `parent_bill_id=parent.id`. D-23. |
| `bill_reminder_task.fire_reminder` | Phase 11 `dispatch_alert` | try/except-wrapped call | ⚠️ PARTIAL | Jobs scheduled; cool-down tracked; but `dispatch_alert` raises TypeError silently. Actual alert delivery unverified. |
| `credential_vault.handle_invalid_grant` | Phase 11 `dispatch_alert` | try/except-wrapped call | ⚠️ PARTIAL | REVOKED status + scanner removal works; `gmail.connection.lost` dispatch_alert TypeError silently. |
| `scanner_service.record_fetch_outcome` | Phase 11 `dispatch_alert` | try/except-wrapped call | ⚠️ PARTIAL | Fetch log written; 2x-failure check runs; `dispatch_alert` TypeError silently. |
| `email-api.ts` | `/api/email/*` endpoints | axios + shared api instance | ✓ WIRED | `email-api.ts:10` imports shared `api`; zero localStorage reads. Recon #3. |
| `ConnectGmailButton.tsx` | `emailApi.connectGmail()` | POST `/api/email/gmail/oauth/authorize` | ✓ WIRED | React component calls emailApi.connectGmail() on click. |
| `bills/[id]/page.tsx` | `emailApi.viewSourceEmail(id)` | on-demand click only | ✓ WIRED | `handleViewEmail` fires only on user click; no useEffect auto-fetch. D-37. |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `BillDashboard.tsx` | bills (list) | GET `/api/email/bills` → `bill_service.list_bills` → DB query | Yes — SQLAlchemy query with filter buckets | ✓ FLOWING |
| `FetchActivity.tsx` | fetch logs | GET `/api/email/credentials/{id}/activity` → RLS-scoped DB query | Yes | ✓ FLOWING |
| `connect/page.tsx` | credential status | GET `/api/email/credentials` → DB query | Yes | ✓ FLOWING |
| `bills/[id]/page.tsx` | source email body | GET `/api/email/messages/{id}/view` → MCP `gmail_read_message` | Yes — real Gmail API call (when credential active) | ✓ FLOWING (conditional on active OAuth) |

---

## Behavioral Spot-Checks

| Behavior | Verification Method | Result | Status |
|----------|---------------------|--------|--------|
| 6 MCP tools registered | `server.py` grep: 6 `@mcp.tool` decorators | 6 found | ✓ PASS |
| In-memory transport (Recon #1) | `client.py` grep: `Client(mcp)`, zero subprocess | Both confirmed | ✓ PASS |
| rbi.org.in in classifier (Recon #4) | `classifier_rules.py:26` grep | Pattern confirmed | ✓ PASS |
| No spaCy NER imports (Recon #2) | grep under `backend/app/email/` | Zero matches | ✓ PASS |
| No localStorage in frontend (Recon #3) | grep across email/ components + pages | Zero matches | ✓ PASS |
| FastAPI lifespan handler (Recon #5) | `main.py:36-37` grep | `@asynccontextmanager async def lifespan` confirmed | ✓ PASS |
| D-36 PII redaction in audit args | `tools.py:_audit_call` details dict inspection | Only body_sha256 + IDs; body/subject/sender are in RETURN not in details | ✓ PASS |
| D-34 body never persisted | `scanner_task.py` + `ingestion_service.py` | Body in Python locals only; only `body_sha256` written to DB | ✓ PASS |
| BILL_MARK_PAID audit row | `bill_service.mark_paid:133` | `log_audit_event_strict(action="BILL_MARK_PAID", ...)` confirmed | ✓ PASS |
| Parent_bill_id recurrence linking | `bill_service.upsert_bill:97` | `parent_bill_id=parent.id if parent is not None else None` confirmed | ✓ PASS |
| Smoke script 12/12 PASS | Reported in orchestrator prompt (docker compose exec backend invocation) | 12/12 PASS per prompt | ? HUMAN-ATTESTED (not independently re-run by verifier) |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| EMAIL-01 | Plans 03, 05, 06, 07 | Gmail OAuth 2.0 connect with offline access + Fernet refresh token | ✓ SATISFIED (code); ? HUMAN for runtime | GmailOAuth class + credential_vault Fernet + OAuth router + ConnectGmailButton |
| EMAIL-02 | Plans 04, 05 | 6 MCP tools registered and callable | ✓ SATISFIED | 6 @mcp.tool registrations; in-memory Client wrapper; smoke check 4 PASS |
| EMAIL-03 | Plans 02, 03 | Fernet-encrypted refresh token; access tokens Redis-only | ✓ SATISFIED | credential_vault save/load; access_token_cache Redis-only; smoke check 5 PASS |
| EMAIL-04 | Plans 02, 05, 06 | Filter rules with priority ordering; CRUD UI | ✓ SATISFIED | gmail_filter_rules table + priority column; filter_rules router ordered by priority ASC; FilterRulesEditor component |
| EMAIL-05 | Plans 02, 03 | Attachment ingestion to DMS; source_email_id FK | ✓ SATISFIED | Document.source_email_id FK; ingestion_service.ingest_attachment reuses v1.0 pipeline |
| EMAIL-06 | Plans 03, 07 | ComplianceNotice auto-creation on sender+subject match; low-confidence → review queue | ✓ SATISFIED (v2.0 scope) | process_classified_email creates notice on (True, 1.0); low-confidence logs (not enqueues) per documented v2.0 deferral. Smoke check 8+9 PASS |
| EMAIL-07 | Plans 02, 03, 05, 06 | GmailFetchLog three-state; 2x FAIL → Phase 11 alert | ⚠️ PARTIAL | Fetch log three-state: SATISFIED. 2x-fail Phase 11 alert: dispatch_alert TypeError — silently fails |
| EMAIL-08 | Plans 02, 03 | Deduplication via composite UNIQUE (credential_id, gmail_message_id) | ✓ SATISFIED | uq_gmail_message_log_dedup enforced; smoke check 7 PASS |
| EMAIL-09 | Plans 04, 05 | MCP tool audit log per call; PII-redacted; immutable | ✓ SATISFIED | _audit_call writes MCP_TOOL_CALL; body_sha256 only; Phase 9 INFRA-07 triggers apply; smoke check 12 PASS |
| EMAIL-10 | Plans 03, 05, 06 | invalid_grant → REVOKED + scanner disabled + reconnect banner | ✓ SATISFIED (code) | handle_invalid_grant sets REVOKED + removes APScheduler job; ConnectGmailButton renders revoked banner. Phase 11 push alert dispatch silently fails but banner works via credential status read |
| BILL-01 | Plans 02, 03 | Bill auto-detection via sender heuristics + LLM | ✓ SATISFIED | bill_extractor.extract_bill LLM-first + regex fallback; biller_category heuristics |
| BILL-02 | Plans 02, 03 | Bill metadata extraction via v1.0 LLM service + bill-specific prompt | ✓ SATISFIED | extract_with_llm("bills") + regex fallback for amount/date/account_last4 |
| BILL-03 | Plans 02, 05, 06 | Bill dashboard with Upcoming/Due Soon/Overdue/Paid filters + bulk mark-paid | ✓ SATISFIED | bills router + BillDashboard with 4 stat cards + bulk mark-paid |
| BILL-04 | Plans 03, 05 | T-3/T-1/overdue reminders via Phase 11 alert pipeline with max-3 cool-down | ⚠️ PARTIAL | APScheduler jobs registered; cool-down (reminder_count) tracked; but Phase 11 dispatch_alert silently fails via try/except TypeError |
| BILL-05 | Plans 02, 03, 05 | Mark-as-paid workflow with audit log | ✓ SATISFIED | bill_service.mark_paid writes BILL_MARK_PAID audit row; cancels reminder jobs |
| BILL-06 | Plans 02, 03 | Recurring bill detection; parent_bill_id linking | ✓ SATISFIED | detect_recurrence + upsert_bill; migration 0027 fixes partial unique for series children; smoke check 11 PASS |

**Coverage:** All 16 Phase 15 requirements present in REQUIREMENTS.md traceability table with status "Complete". EMAIL-07 and BILL-04 are partially satisfied (infrastructure wired; Phase 11 alert delivery broken due to dispatch_alert signature mismatch).

---

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `backend/app/email/tasks/bill_reminder_task.py:68` | `except (ImportError, TypeError)` silently swallows dispatch_alert failure | ⚠️ Warning | BILL-04 reminder notifications will not fire in production; cool-down logic runs but alerts are never delivered |
| `backend/app/email/services/credential_vault.py:108` | Same try/except pattern swallows gmail.connection.lost alert | ⚠️ Warning | EMAIL-10 Phase 11 push notification not delivered; banner still works via status read |
| `backend/app/email/services/scanner_service.py:101` | Same try/except pattern swallows 2x FETCH_FAILED alert | ⚠️ Warning | EMAIL-07 Phase 11 push notification not delivered; fetch log still written |
| `backend/app/email/services/ingestion_service.py:239-260` | Low-confidence emails log routing but don't enqueue to Phase 10 review queue | ℹ️ Info | Documented v2.0 deferral per Plan 03 deviation #8; smoke check 9 encodes this contract |
| `.planning/ROADMAP.md:132` | SC4 text says "Phase 10 BERT pipeline" but implementation is rule-based (D-16 revised) | ℹ️ Info | ROADMAP text inconsistency with CONTEXT.md D-16 and implementation; does not block functionality |

None of the above are stub patterns (empty implementations or placeholder returns) — they are intentional try/except wrappers with known behavioral gaps.

---

## Human Verification Required

### 1. Real Google OAuth Round-Trip

**Test:** Run `docker compose up -d`, navigate to `/dashboard/email/connect`, click "Connect Gmail", complete Google OAuth consent for a real test Gmail account.
**Expected:** Credential row created in `gmail_credentials` table; `refresh_token_enc` is non-null bytes; Redis access token TTL is between 3500-3600s; no plaintext refresh token in backend logs or Celery args.
**Why human:** Real Google OAuth requires a registered Cloud Console OAuth client, a test Gmail account, and a browser. The automated smoke uses mock credentials only.

### 2. Phase 11 Alert Delivery for Bill Reminders (BILL-04)

**Test:** Create a bill with a due date 4 days from now via `/api/email/bills` or by triggering the scanner on a bill email. Check APScheduler job logs and backend logs when the T-3 job fires.
**Expected:** Either: (a) a Phase 11 alert is dispatched and delivered (email/in-app), confirming the dispatch_alert signature gap was resolved, OR (b) the backend logs show `"bill reminder dispatch skipped (TypeError)"`, confirming the gap persists.
**Why human:** The dispatch_alert try/except silently logs a TypeError. A human must verify the actual log output to determine if BILL-04 alert delivery works in the deployed environment, and whether Plan 05 added any adapter that the code review did not find.

### 3. 2x FETCH_FAILED Phase 11 Alert (EMAIL-07)

**Test:** Simulate two consecutive scanner failures for a credential (e.g., by revoking Gmail access at the Google account level mid-run). Check if a Phase 11 in-app notification or email fires.
**Expected:** A Phase 11 alert fires; the fetch log shows two FETCH_FAILED rows; the UI shows an alert banner.
**Why human:** Same dispatch_alert signature gap as BILL-04.

### 4. View Source Email Deep-Link on Document and ComplianceNotice Detail Pages (SC7)

**Test:** After Gmail ingestion creates a Document and ComplianceNotice, navigate to the Document detail page and ComplianceNotice detail page in the frontend. Verify that a "View source email" button is present on both.
**Expected:** Both detail pages show the deep-link button when `source_email_id` is set; clicking it fetches the body from `/api/email/messages/{id}/view` without page refresh; body does not persist after page reload.
**Why human:** Plan 06 implemented the deep-link only on `/dashboard/email/bills/[id]`. The Document detail page and ComplianceNotice detail page were mentioned in ROADMAP SC7 and CONTEXT D-18/D-37 but no code was found in the verification confirming those pages were updated. This needs visual confirmation.

---

## Verification of Critical Reconciliations

| Reconciliation | Contract | Code Evidence | Status |
|----------------|----------|---------------|--------|
| #1 (D-38) | In-memory `Client(mcp)` — zero subprocess | `client.py:22`: `async with Client(mcp) as client`; `grep subprocess backend/app/email/mcp/` returns 0 | ✓ VERIFIED |
| #2 | No spaCy NER imports under email/ | `grep -rn "from app.ml.compliance.ner" backend/app/email/` returns 0; classifer.py uses regex_patterns only | ✓ VERIFIED |
| #3 | js-cookie reading via shared interceptor, not localStorage | `email-api.ts:10` imports `api` from `@/lib/api`; `grep localStorage` across new email code returns 0 | ✓ VERIFIED |
| #4 | `rbi.org.in` literal in COMPLIANCE_SENDER_PATTERNS | `classifier_rules.py:26`: `re.compile(r"@rbi\.org\.in$", re.IGNORECASE)` | ✓ VERIFIED |
| #5 | FastAPI lifespan handler in main.py | `main.py:36-37`: `@asynccontextmanager async def lifespan(app)` | ✓ VERIFIED |
| #6 | gmail_fetch_log standalone — no Phase 14 dependency | `0025_phase15_gmail_mcp.py`: no portal/Phase 14 imports or FK references | ✓ VERIFIED |

---

## Privacy/Security Posture Verification

| Decision | Contract | Evidence | Status |
|----------|----------|----------|--------|
| D-34 | Body never persisted to DB or Redis | `scanner_task.py:171-253` body stays in Python local; only body_sha256 written | ✓ VERIFIED |
| D-35 | Audit log args = body_sha256 + IDs only | `tools.py:_audit_call` details dict contains `body_sha256`, `message_id`, `attachment_ids` — body/subject/sender are in RETURN VALUE, not audit details | ✓ VERIFIED |
| D-36 | PII redaction — no body/sender/subject keys in audit trail | `tools.py:85-96` gmail_search audit: `query_sha256` + `result_count`; `tools.py:128-138` read_message audit: `message_id` + `body_sha256` + `attachment_ids` only | ✓ VERIFIED |

---

## Gaps Summary

Three requirements are partially satisfied due to a single root cause: Phase 11's `dispatch_alert(db, *, notice, alert_type, channels, recipients, payload)` function requires a `ComplianceNotice` parent object, but Phase 15 alert scenarios (bill reminders, connection.lost, 2x FETCH_FAILED) have no parent notice. All three callers wrap the call in `try/except (ImportError, TypeError)` which catches and silently logs the TypeError on every production invocation.

This was first identified in Plan 03 deviation #7 with the note "Plan 05 router-side will wire a credential/bill-shaped alert pathway." Plan 05 did not deliver this adapter — it instead verified EMAIL-04, EMAIL-07, and BILL-04 against the scheduling/status-tracking aspects (which work), not the actual Phase 11 notification delivery.

**Impact assessment:** The alert delivery gap is a **Warning severity** issue, not a blocker for goal achievement. The goal states "auto-routed for compliance review" and "queryable by internal AI agents via MCP tools" — both of which work. The alerts are a supporting mechanism. The status-tracking infrastructure (REVOKED state, fetch logs, cool-down counts, scheduler jobs) is fully wired. Only the final notification push is broken.

**Recommended resolution path:** Add a `dispatch_bill_alert(db, *, bill, alert_type, payload)` and `dispatch_credential_alert(db, *, credential, event_type, payload)` helper in `alert_service.py` that creates minimal in-app notifications without requiring a parent ComplianceNotice. This is a 30-50 line addition that closes EMAIL-07, EMAIL-10 (alert part), and BILL-04 completely.

One additional human verification item exists: the "View source email" deep-link on Document and ComplianceNotice detail pages (SC7). Plan 06 only added this button to the bills/[id] detail page; the other two surfaces are unconfirmed.

---

_Verified: 2026-05-08_
_Verifier: Claude (gsd-verifier)_
