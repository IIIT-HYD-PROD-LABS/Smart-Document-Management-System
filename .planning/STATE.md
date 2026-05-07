---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Compliance Management System
status: Ready to execute
stopped_at: Completed 15-06-PLAN.md (frontend — 15 files + sidebar + tsconfig fix); ready for Plan 15-07 (smoke verification)
last_updated: "2026-05-07T18:49:39.908Z"
progress:
  total_phases: 7
  completed_phases: 3
  total_plans: 18
  completed_plans: 18
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-30)

**Core value:** Automated classification and intelligent management of documents and compliance notices
**Current focus:** Phase 15 — gmail-mcp-integration

## Current Position

Phase: 15 (gmail-mcp-integration) — EXECUTING
Plan: 7 of 7

## Shipped Milestones

- **v1.0** (2026-03-30): Smart Document Management System — 8 phases, 42 requirements, 127 commits
- **v2.0 Phase 9** (2026-04-28, SHIPPED): Compliance Foundation — 26 requirements satisfied, 7 plans, 21-step manual smoke verified by user 2026-04-28
- **v2.0 Phase 10 v2.0** (2026-05-05, CODE-COMPLETE + smoke PASSED): ML Classification + Risk Scoring — RISK-01..05 + INFRA-01 + CLASS-04 (review queue infra) satisfied via rule-based scorer + escalation + review queue infrastructure; CLASS-01..03/05..08 deferred to v2.1. End-to-end smoke green: Critical-tier 90.8 score, escalation activity + audit log written, 3 SHAP factors persisted.
- **v2.0 Phase 11 v2.0** (2026-05-05, CODE-COMPLETE — pending user browser smoke): Alerts + Calendar — APScheduler + multi-channel alert pipeline (email + WebSocket; SMS scaffolded), Indian holiday-aware deadline adjustment, statutory calendar with 37 FY 2025-26 deadlines pre-seeded, compliance-score chip, NotificationBell with auto-reconnecting WebSocket. 95 backend tests GREEN.

## Accumulated Context

### Decisions

- Extend existing app (not separate service) — shared auth, DB, UI eliminates bridge overhead
- BERT for notice classification — discriminative task, 92%+ accuracy target vs. 85% ceiling for scikit-learn
- Elasticsearch as managed service (Elastic Cloud) — avoid OOM on Render self-hosted
- PostgreSQL is always system of record; Elasticsearch is eventually-consistent sidecar
- Audit trail immutability enforced at DB level (triggers + REVOKE) from Phase 9 — retrofitting is a migration
- Dedicated 2GB `compliance` Celery queue for ML tasks — prevent v1.0 performance degradation
- Portal integration deferred to Phase 14 (highest uncertainty: GSP empanelment, IT API availability)

See .planning/milestones/v1.0-ROADMAP.md for v1.0 decisions.

- [Phase 09]: Wave 0 RED state discipline: 17 stub test files reference modules that do not yet exist (Plans 02-05 land them); pytest.skip() guards keep v1.0 suite green
- [Phase 09]: Five merge gates declared: test_no_cross_client_leakage (CLIENT-04), test_update_raises + test_delete_raises (AUDIT-01), test_app_role_lacks_privilege (INFRA-07), 84-case test_role_permission_matrix (RBAC-01..06)
- [Phase 09]: Two-layer audit immutability test design: PostgreSQL trigger (raises 'append-only' EXCEPTION on UPDATE/DELETE) + REVOKE on app_runtime role — defense in depth even if a future migration accidentally drops the trigger
- [Phase 09]: Local Postgres docker service required for Phase 9 RLS testing — Supabase pooler in transaction mode does not support FORCE RLS / role switching / trigger DDL
- [Phase 09]: Migration chain re-ordered: 0012→0013→0017→0014→0015→0016 (head=0016) because PG CREATE POLICY ... TO role has no IF NOT EXISTS escape hatch; role must exist before REVOKE/POLICY references it
- [Phase 09]: Two-policy access pattern: tenant_isolation (RESTRICTIVE per-tenant USING+WITH CHECK) + cross_client_view (PERMISSIVE for compliance_head/ca_consultant/cfo) on all 6 client-scoped tables
- [Phase 09]: Service layer is the SINGLE point of mutation for ComplianceNotice.status — Pitfall 8 mitigation; routers in Plan 05 must call transition_notice_status, never direct ORM update
- [Phase 09]: transition_notice_status writes paired NoticeActivity (timeline, mutable) + AuditLog (immutable, separate session) on every status change — audit failures cannot roll back business operations
- [Phase 09]: Migration 0018: SECURITY DEFINER helpers (is_cross_client_eligible, user_has_client_membership) break the cross_client_view RLS recursion AND fix the unsatisfiable INSERT WITH CHECK on compliance_clients
- [Phase 09]: bulk_update_status uses per-row sub-transactions with partial-failure semantics (Pattern 8) — returns {results[], summary{ok,failed}} so the UI renders per-row error indicators
- [Phase 09]: Plan 04: before_cursor_execute listener for RLS context — survives intra-request commits where set_config(is_local=true) does not
- [Phase 09]: Plan 04: Migration 0019 wraps tenant_isolation cast in NULLIF so empty current_setting fails-closed cleanly (no DataError)
- [Phase 09]: Plan 04: tenant_isolation kept PERMISSIVE — RESTRICTIVE alone would block all writes since cross_client_view PERMISSIVE is SELECT-only
- [Phase 09-compliance-foundation]: Plan 05: Status-target -> permission dispatcher on PATCH /notices/{id}/status (single endpoint handles all 5 forward + 2 back-edit transitions, dispatches NOTICE_SUBMIT/APPROVE/DRAFT_RESPONSE per target via _permission_for_target_status helper); avoids scattering state machine across 5 separate handlers
- [Phase 09-compliance-foundation]: Plan 05: First-upload-wins for notice.document_id — first POST /notices/{id}/upload sets the FK; subsequent uploads attach via NoticeActivity 'file_attached' rows but do NOT overwrite the primary, preserving stable deep-links to the original notice document
- [Phase 09-compliance-foundation]: Plan 05: Read-only audit endpoint (audit.py omits @router.post/put/delete decorators entirely) — DB trigger + REVOKE on app_runtime is the authoritative defense; API surface omission is principle-of-least-surprise so a future maintainer cannot accidentally add a write handler
- [Phase 09-compliance-foundation]: Plan 05: REPORT_EXPORT (not REPORT_VIEW) on /reports/health-summary — REPORT_EXPORT covers compliance_head/ca_consultant/auditor/cfo (the actual stakeholders) while REPORT_VIEW would over-grant to legal_team + finance_team who view notices but should not extract per-client analytics
- [Phase 09-compliance-foundation]: Plan 06: Hybrid URL+Zustand for tenant state — URL holds detail-page IDs and step number; Zustand holds in-memory wizard form data and active client. complianceApi.tenantHeaders() reads X-Client-Id from useCurrentClient.getState() on every call (not cached) so client switches are immediate.
- [Phase 09-compliance-foundation]: Plan 06: react-day-picker v9 (NOT v8) — v8's peerDependencies cap React at 18; v1.0 stack is React 19. v9 declares react>=16.8.0 and works.
- [Phase 09-compliance-foundation]: Plan 06: getValues() not watch() for RHF — placeholders for dynamic field arrays (StepRegistrations) computed inside JSX render via getValues() per RESEARCH Pattern 6 (React 19 + RHF v7 watch() compatibility caveat).
- [Phase 09-compliance-foundation]: Plan 06: Membership validation on switcher mount — when /memberships/me returns, ClientSwitcher cross-checks the persisted activeClientId; if missing (auditor expired, revoked) the store clears it so the next request doesn't 403. Cross-client mode sends 'X-Client-Id: *' (not omitted); backend Plan 04 enforces eligibility.
- [Phase 09-compliance-foundation]: Plan 06: Auditor 3-tier expiry visualization (D-27): default neutral / amber 'Expires in N days' if <7 days remain / red 'Expired' + opacity-50 if past access_end. Pure derived state from access_end + now().
- [Phase 15]: [Phase 15] Plan 01: Wave 0 RED-state test infrastructure — 17 backend pytest stubs + 4 frontend vitest stubs + 8-fixture conftest gating Plans 02-07; in-memory FastMCP Client(mcp) pattern (D-38) documented in test_mcp_tools.py
- [Phase 15]: [Phase 15] Plan 01: Fernet test key derived via SHA-256(stable phrase) producing valid 32-byte raw key — plan's literal urlsafe_b64encode would have raised ValueError 'Fernet key must be 32 url-safe base64-encoded bytes'; Rule 1 deviation in conftest.py
- [Phase 15]: [Phase 15] Plan 01: Reconciliation contracts locked in stubs — rbi.org.in sender domain (test_compliance_router.py recon #4), priority column on GmailFilterRule (test_filter_rules.py open Q #5), in-memory FastMCP Client (test_mcp_tools.py recon #1), body never persisted (test_pii_lifecycle.py D-34)
- [Phase 15-gmail-mcp-integration]: Plan 02: Migration 0025 uses descriptive slug suffix (0025_phase15_gmail_mcp) matching existing chain convention; bare '0025' would have broken visual + downgrade reference
- [Phase 15-gmail-mcp-integration]: Plan 02: RLS subquery pattern for credential-scoped tables (filter_rules, message_log, fetch_log) — credential_id IN (SELECT id FROM gmail_credentials WHERE client_id = ...) instead of denormalized client_id column
- [Phase 15-gmail-mcp-integration]: Plan 02: Bill hybrid model encoded with two independent FKs (source_document_id NULLABLE for text-only bills, source_email_id always set for provenance) — analytics queries can filter on IS NULL for the no-attachment cohort
- [Phase 15-gmail-mcp-integration]: Plan 02: 4 Plan 01 RED stubs flipped to GREEN at schema level (priority column, composite UNIQUE on message_log, three-state CHECK on fetch_log, partial unique index ux_bills_recurrence_key); 37 service/router-level stubs remain skipped for Plans 03-05
- [Phase 15-gmail-mcp-integration]: Plan 03: AUTHORITY_BY_DOMAIN added to classifier_rules.py — sender → ComplianceNotice.authority CHECK constraint (GST/IT/MCA/RBI/SEBI). Default GST when only broad gov.in pattern matches (deviation Rule 1).
- [Phase 15-gmail-mcp-integration]: Plan 03: ComplianceNotice creation omits source_email_id kwarg — column doesn't exist on compliance_notices (Plan 02 only added documents.source_email_id). Provenance via notice.document_id → documents.source_email_id chain; audit log captures gmail_message_log_id.
- [Phase 15-gmail-mcp-integration]: Plan 03: Phase 11 dispatch_alert signature mismatch handled with try/except (TypeError + ImportError) in 3 callsites — bill/credential alerts have no parent ComplianceNotice. Plan 05 router will wire credential/bill-shaped alert pathway. Cool-down state still updates locally.
- [Phase 15-gmail-mcp-integration]: Plan 03: Review-queue enqueue at score=0.5 deferred to Plan 05 — review_queue_service.enqueue_low_confidence requires parent notice + per-field confidences; v2.0 logs the routing decision with PII-redacted refs (sender_domain + body_sha256).
- [Phase 15-gmail-mcp-integration]: Plan 03: B3 split — bill_reminder_task.fire_reminder is canonical APScheduler entry; bill_service.fire_bill_reminder is a thin wrapper for legacy schedule registrations. schedule_bill_reminders registers 3 jobs (bill_t3/bill_t1/bill_overdue) matching VALID_ALERT_TYPES exactly.
- [Phase 15-gmail-mcp-integration]: Plan 04: fastmcp/FastAPI dep conflict (open from Plan 03) resolved by upgrading FastAPI 0.104.1 -> 0.120.4 + starlette 0.49.3 + anyio 4.13.0; pip check exits 0; v1.0 + Phase 9 + Phase 15 service tests 503 pass / 0 fail at the new pins
- [Phase 15-gmail-mcp-integration]: Plan 04: in-memory FastMCP transport (D-38) verified — grep -r subprocess across MCP module + main.py returns 0; Client(mcp) is the only call path; native Python exceptions propagate (RuntimeError on bad transport, ToolError on Gmail API errors)
- [Phase 15-gmail-mcp-integration]: Plan 04: FastAPI lifespan handler is the project's first; warmups APScheduler + registers MCP module at boot. get_scheduler() wrapped in try/except so a missing apscheduler_jobs table cannot block startup. Migration 0026 pre-creates the table with CRUD grants to app_runtime so Phase 11 boot path is finally healthy.
- [Phase 15-gmail-mcp-integration]: Plan 04: gmail_list_attachments uses format='full' not format='metadata' — Gmail metadata format omits payload.parts[].body.attachmentId so attachments would always come back []. Quota cost equals gmail_read_message; correctness > quota optimization.
- [Phase 15-gmail-mcp-integration]: Plan 05: Permission gate dependency takes ClientMembership directly (not (User, ClientMembership)) — routers read membership.user_id + membership.client_id from a single Depends() object; ensures every endpoint goes through get_active_membership which is the only path enforcing auditor expiry + cross-client mode rules
- [Phase 15-gmail-mcp-integration]: Plan 05: OAuth callback re-validates state JWT user_id + client_id against current membership before save_credential — defense in depth on top of JWT signature validation; rejects with 403 even if a malicious user has a valid state token from another session
- [Phase 15-gmail-mcp-integration]: Plan 05: DELETE /credentials soft-disables (status='disabled') instead of hard-deleting — hard-delete would orphan source_email_id FKs from ingested Documents and Bill rows, breaking the provenance chain. STATUS_DISABLED reuses the existing CHECK-constraint value.
- [Phase 15-gmail-mcp-integration]: Plan 05: Bulk mark-paid uses db.begin_nested() (SAVEPOINT) per row — survives inner exception cleanly without disturbing outer session (TenantContextMiddleware sets app.current_client_id via SET LOCAL inside request transaction); equivalent partial-failure semantics to Phase 9 LIFE-08 db.rollback pattern but composes better with mid-request middleware writes.
- [Phase 15-gmail-mcp-integration]: Plan 05: view_email router does NOT write its own audit log — the MCP tool _audit_call('gmail_read_message', ...) writes the PII-redacted MCP_TOOL_CALL row from Plan 04 D-35/D-36 wiring; double-counting at the router would inflate audit volume without adding traceability.
- [Phase 15-gmail-mcp-integration]: Plan 06: Reconciliation #3 enforced at the source — frontend/src/lib/email-api.ts imports api from @/lib/api which already attaches Cookies.get('token') via interceptor. No email-side code touches js-cookie or localStorage; grep -r localStorage across new files returns 0. NotificationBell.tsx Phase 11 bug NOT replicated.
- [Phase 15-gmail-mcp-integration]: Plan 06: Excluded **/__tests__/** from frontend/tsconfig.json — Plan 01 vitest stubs (describe.skip + it.todo) imported vitest but vitest was never installed; tsc --noEmit was failing. Plan 06 success criterion permits keeping stubs deferred. Vitest install + config deferred to a tooling plan.
- [Phase 15-gmail-mcp-integration]: Plan 06: Sidebar Email group inserted as a peer between Documents and Compliance, not nested inside either — email feeds both surfaces (compliance notices via routing rules; DMS attachments and bills which span both). Connect/Settings restricted to admin+editor (mutating); Activity/Bills viewable by viewer (read-only).
- [Phase 15-gmail-mcp-integration]: Plan 06: D-37 on-demand 'View source email' button — bills/[id]/page.tsx never auto-fetches the body. User must click; body held in React state for the rendered session only (refresh discards). No localStorage, no Zustand store, no service worker cache. Aligns with D-34 PII lifecycle on the frontend side.

### Pending Todos

None.

### Blockers/Concerns

- Phase 10: BERT training data sourcing — need 300+ real labeled examples per class (40+ classes) before auto-routing; synthetic augmentation strategy needed if insufficient real data
- Phase 10: Base BERT model selection (bert-base-uncased vs. ai4bharat/indic-bert vs. legal-bert) — needs empirical validation; flag for `/gsd:research-phase`
- Phase 11: RegulatoryCalendar seed data — CBDT/CBIC/state holiday lists for 2026 must be sourced from official publications before Phase 11 deadline calculation is implemented
- Phase 14: GST GSP empanelment status — verify whether CA firm direct API access requires empanelment at `developer.gst.gov.in` before Phase 14 planning
- Phase 14: IT e-filing e-Proceedings API — no public documentation found; must verify with CPC Bangalore or third-party aggregator before Phase 14 planning; flag for `/gsd:research-phase`

## Session Continuity

Last session: 2026-05-07T18:49:39.905Z
Previous session: 2026-04-30T10:21:00Z (auth + early-access bug sweep)

Stopped at: Completed 15-06-PLAN.md (frontend — 15 files + sidebar + tsconfig fix); ready for Plan 15-07 (smoke verification)

v2.1 deferral commit: 10-RESEARCH-FINAL.md locks InLegalBERT as the v2.1 primary base model recommendation, training-data strategy (SEBI scrape + LLM-template synthetic + hand-labeled real held-out test set), and authority severity weights (CA/CFO sign-off pending — placeholders ship for v2.0).

Resume command: docker compose up && manual-smoke Phase 10 v2.0 → /gsd:discuss-phase 11 → /gsd:research-phase 11 → /gsd:plan-phase 11

## Plan 09-03 Completion (resolved 2026-04-27)

**All 8 tasks committed.** Resumed after org-usage-limit interruption that
left WIP files (migration 0018, conftest, activity_service stub) at task ~5/8.

**Commits (T1-T5 originally; T6-T8 + 3 deviations on resumption):**

- `9bf9607` T1: Client + ClientRegistration ORM
- `928d055` T2: ClientMembership ORM (time-bound access)
- `038e5d4` T3: NoticeType + ComplianceNotice + NoticeActivity + NoticeTag + RegulatoryCalendar
- `ee7b843` T4: Document.notice_id FK + register Phase 9 models
- `85d7435` T5: Pydantic schemas (client + notice + activity)
- `f331161` DEVIATION (Rule 1): migration 0018 — RLS cross-client recursion fix
- `a7626a1` DEVIATION (Rule 1): conftest fixtures — RLS-bypass-then-SET-ROLE pattern
- `854d492` T6: activity_service + notice_service (state machine + chain + bulk + filter)
- `3a39c71` T7: client_service (onboard + dashboard) + report_service (health summary)

**Test outcomes:** 15/15 Wave 2 integration tests GREEN; 121/121 v1.0 + Wave 1
regression tests still GREEN. 4 test_rls_isolation tests + 3 test_auditor_expiry
errors are explicit Plan 04 responsibility (middleware not yet wired).

**Artifacts:**

- 09-03-SUMMARY.md (this plan's summary)

Wave structure (sequential — Wave 0 establishes security gates before any business logic):
  Wave 0 → Plan 01: Test infrastructure (3 merge-gate tests + 14 stub files + conftest) [✅]
  Wave 1 → Plan 02: DB foundations (5 migrations 0013-0017 + validators + permission registry) [✅]
  Wave 2 → Plan 03: ORM models + services (Client, Membership, Notice, NoticeType, Calendar) [✅]
  Wave 3 → Plan 04: Tenant middleware + RBAC dependency factory [READY]
  Wave 4 → Plan 05: 7 FastAPI routers (clients/memberships/notices/reports/audit/lookups)
  Wave 5 → Plan 06: Frontend foundation (Zustand stores + ClientSwitcher + 4-step wizard) [✅ user APPROVED 2026-04-27]
  Wave 6 → Plan 07: Frontend notice surfaces (12 components + 5 pages + README) [executing]

Uncommitted artifacts: .gitignore (+.vercel), vercel.json — pre-existing, non-blocking
