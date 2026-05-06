---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Compliance Management System
status: Phase 10-13 v2.0 CODE-COMPLETE + smokes PASSED. SECOND hardening pass shipped: 5 CRITICAL + 9 HIGH fixes from 5-agent end-to-end audit covering Phase 1-13. Closed cross-user document leak (CRIT-1), APScheduler RLS regression (CRIT-2), audit dead-letter durability (CRIT-3), regulatory audit failure visibility (CRIT-4), LLM extraction status mislabeling (CRIT-5), plus 9 Tier B fixes. 163 backend tests GREEN. See HARDENING-PLAN-2.md.
stopped_at: "v2.0 Phases 10-13 CODE-COMPLETE 2026-05-05. Phase 13 ships: PostgreSQL-FTS-backed unified cross-entity search across compliance_notices + documents, with 4 new endpoints (/api/compliance/search/unified + /api/compliance/reports/{penalty-by-authority,notice-volume-by-status,response-time}); migration 0023 adds search_vector TSVECTOR + GIN index + trigger to compliance_notices (mirrors Phase 4 documents pattern); frontend cross-entity search page at /dashboard/compliance/search + reports analytics cards (penalty by authority, notice volume by status, response time percentiles). Phase 13 v2.1 deferrals binding: Elastic Cloud, outbox pattern, indexer worker, daily reconciliation, ES degraded-mode banner, severity-weighted compliance score, real-time search-as-you-type, vector/semantic search, server-side snippet sanitization. Phase 13 v2.0 chosen split per 13-RESEARCH-FINAL.md: criteria 1-3 (unified search + cross-system + sub-3s reports) deliverable today on PG; criteria 4-5 (ES fallback + reconciliation) are scale infrastructure that only matter once ES exists. Saves recurring Elastic Cloud subscription until v2.1 evidence-based justification. End-to-end smoke PASSED: 'GST' query returned 3 notice + 8 document hits ranked correctly (top rank 0.8529); SEBI query filtered to single critical notice; aggregations returned correct shapes. 161 backend tests GREEN. Frontend XSS hardening: search snippets render as plain text (HTML stripped) — security hook caught the unsafe HTML render path on first commit and the code was rewritten before review. Migration head=0023_phase13_search_vector_on_notices. Phase 14 CONTEXT seeded with external blockers (GSP empanelment, IT API access); Phase 15 CONTEXT seeded 2026-04-28. Next: /gsd:discuss-phase 14 once external decisions land, OR /gsd:discuss-phase 15 (Gmail MCP — fewer blockers)."
last_updated: "2026-05-06T18:30:00.000Z"
progress:
  total_phases: 7
  completed_phases: 1
  v2_phase_10_v2_0_code_complete_at: "2026-05-05"
  v2_phase_11_v2_0_code_complete_at: "2026-05-05"
  v2_phase_12_v2_0_code_complete_at: "2026-05-05"
  v2_phase_13_v2_0_code_complete_at: "2026-05-05"
  v2_0_1_patch_user_facing_fixes_at: "2026-05-06"
  v2_0_1_patch_supabase_advisor_at: "2026-05-06"
  total_plans: 15
  completed_plans: 15
  percent: 63
  v2_phase_9_shipped_at: "2026-04-28"
  alembic_head: "0024_supabase_security_advisor_fixes"
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-30)

**Core value:** Automated classification and intelligent management of documents and compliance notices
**Current focus:** Phase 09 — compliance-foundation

## Current Position

Phase: 11 (alerts-and-calendar) — v2.0 CODE-COMPLETE 2026-05-05.
Phases 12, 13, 14 CONTEXTS seeded (12 unblocked, 14 has hard external blockers).
Phase 15 CONTEXT was seeded 2026-04-28.
Next:
  1. Manual user smoke of Phase 10 + 11 (browser flows): create notice, transition to Under Review, see ConfidenceBadge + risk panel, navigate to /calendar (37 deadlines visible), open NotificationBell (WebSocket connects).
  2. /gsd:discuss-phase 12 → /gsd:research-phase 12 → /gsd:plan-phase 12 (Response Drafting + Evidence Management).
  3. Phase 14 awaits external decisions (GSP empanelment, IT API access) — see 14-CONTEXT.md Open Blockers.

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

### Pending Todos

None.

### Blockers/Concerns

- Phase 10: BERT training data sourcing — need 300+ real labeled examples per class (40+ classes) before auto-routing; synthetic augmentation strategy needed if insufficient real data
- Phase 10: Base BERT model selection (bert-base-uncased vs. ai4bharat/indic-bert vs. legal-bert) — needs empirical validation; flag for `/gsd:research-phase`
- Phase 11: RegulatoryCalendar seed data — CBDT/CBIC/state holiday lists for 2026 must be sourced from official publications before Phase 11 deadline calculation is implemented
- Phase 14: GST GSP empanelment status — verify whether CA firm direct API access requires empanelment at `developer.gst.gov.in` before Phase 14 planning
- Phase 14: IT e-filing e-Proceedings API — no public documentation found; must verify with CPC Bangalore or third-party aggregator before Phase 14 planning; flag for `/gsd:research-phase`

## Session Continuity

Last session: 2026-05-05T10:00:00Z (Phase 10 v2.0 ship — review queue infra + auto-escalation + frontend SHAP UI)
Previous session: 2026-04-30T10:21:00Z (auth + early-access bug sweep)

Stopped at: 2026-05-05 — Phase 10 v2.0 code-complete. Three plans (10-01 review queue backend, 10-02 auto-escalation, 10-03 frontend SHAP UI) all landed. Backend delivers: NoticeReviewQueue ORM + Pydantic schemas + service layer + 3 review endpoints (/api/compliance/review/{pending,id,id/assign}); escalation.py with should_escalate + escalate functions wired into compliance_tasks.classify_and_score_notice; NOTICE_REVIEW permission added to compliance_head, ca_consultant, legal_team. Frontend delivers: ConfidenceBadge + WhyThisRiskScore + RiskTierDot upgrade (with motion-safe pulse on Critical) + /dashboard/compliance/review page + sidebar nav entry. 82 unit + service tests GREEN; integration tests for client_with_membership fixture error on Supabase pooler (pre-existing — needs local Postgres for SET ROLE). Pre-Phase-10 Wave 0 already had migration 0020, the ML columns ORM, the compliance-worker Celery service, the rule-based risk scorer, regex_patterns, and 3 supporting test files.

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
