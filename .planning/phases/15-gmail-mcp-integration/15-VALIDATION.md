---
phase: 15
slug: gmail-mcp-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-07
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from `15-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 (backend) · vitest + Testing Library (frontend) |
| **Config file** | `backend/pyproject.toml` · `frontend/vitest.config.ts` |
| **Quick run command** | `cd backend && pytest -x tests/compliance/email/ -m "not integration"` |
| **Full suite command** | `cd backend && pytest tests/ && cd ../frontend && pnpm vitest run` |
| **Estimated runtime** | ~45s quick · ~6 min full |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest -x tests/compliance/email/ -m "not integration"` (quick — non-integration tests only)
- **After every plan wave:** Run `cd backend && pytest tests/compliance/email/` (includes integration with Postgres + Redis)
- **Before `/gsd:verify-work`:** Full suite must be green (backend 389+ existing + new Phase 15 tests; frontend vitest)
- **Max feedback latency:** 45 seconds (quick) · 360 seconds (full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 15-01-01 | 01 | 0 | EMAIL-01..10 | unit (stubs) | `pytest -x tests/compliance/email/test_oauth_flow.py` | ❌ W0 | ⬜ pending |
| 15-01-02 | 01 | 0 | EMAIL-03/07/09 | unit (stubs) | `pytest -x tests/compliance/email/test_credential_vault.py` | ❌ W0 | ⬜ pending |
| 15-01-03 | 01 | 0 | EMAIL-04/05/06/08 | unit (stubs) | `pytest -x tests/compliance/email/test_scanner_dedup.py` | ❌ W0 | ⬜ pending |
| 15-01-04 | 01 | 0 | EMAIL-02/09 | unit (stubs) | `pytest -x tests/compliance/email/test_mcp_tools.py` | ❌ W0 | ⬜ pending |
| 15-01-05 | 01 | 0 | EMAIL-06 | unit (stubs) | `pytest -x tests/compliance/email/test_compliance_router.py` | ❌ W0 | ⬜ pending |
| 15-01-06 | 01 | 0 | BILL-01..06 | unit (stubs) | `pytest -x tests/compliance/email/test_bill_extraction.py` | ❌ W0 | ⬜ pending |
| 15-01-07 | 01 | 0 | BILL-04 | unit (stubs) | `pytest -x tests/compliance/email/test_bill_recurrence.py` | ❌ W0 | ⬜ pending |
| 15-01-08 | 01 | 0 | EMAIL-09 (PII) | unit (stubs) | `pytest -x tests/compliance/email/test_audit_pii_redaction.py` | ❌ W0 | ⬜ pending |
| 15-01-09 | 01 | 0 | EMAIL-09 (immutability) | unit (stubs) | `pytest -x tests/compliance/email/test_audit_immutability.py` | ❌ W0 | ⬜ pending |
| 15-01-10 | 01 | 0 | EMAIL-10 | unit (stubs) | `pytest -x tests/compliance/email/test_invalid_grant_handling.py` | ❌ W0 | ⬜ pending |
| 15-02-* | 02 | 1 | EMAIL-03/05/07 + BILL-01..06 | migrations | `alembic upgrade head` + introspection tests | ✅ pytest | ⬜ pending |
| 15-03-* | 03 | 2 | EMAIL-01..10 (services) | unit + integration | `pytest tests/compliance/email/test_*service*.py` | ✅ pytest | ⬜ pending |
| 15-04-* | 04 | 2 | EMAIL-02/09 (MCP tools) | integration | `pytest tests/compliance/email/test_mcp_*.py` | ✅ pytest | ⬜ pending |
| 15-05-* | 05 | 3 | EMAIL-01..10 (routers) | integration | `pytest tests/compliance/email/test_router_*.py` | ✅ pytest | ⬜ pending |
| 15-06-* | 06 | 3 | BILL-01..06 (frontend) | vitest | `pnpm vitest run --dir src/components/email` | ✅ vitest | ⬜ pending |
| 15-07-* | 07 | 4 | end-to-end smoke | smoke test | `python scripts/smoke_phase15_v20.py` | ❌ Wave 4 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements (Phase 15 Test Infrastructure)

- [ ] `backend/tests/compliance/email/__init__.py`
- [ ] `backend/tests/compliance/email/conftest.py` — fixtures: mock Gmail API responses, sample OAuth tokens, sample email payloads (compliance + bills + spam), Fernet test key
- [ ] `backend/tests/compliance/email/test_oauth_flow.py` — OAuth round-trip with state CSRF + offline access (EMAIL-01)
- [ ] `backend/tests/compliance/email/test_credential_vault.py` — Fernet round-trip; refresh token never plaintext in logs/queries; access token only in Redis (EMAIL-03)
- [ ] `backend/tests/compliance/email/test_scanner_dedup.py` — composite UNIQUE on (credential_id, gmail_message_id); SHA-256 dedup per attachment within credential (EMAIL-08)
- [ ] `backend/tests/compliance/email/test_mcp_tools.py` — 6 tool registration; argument schema; error envelope; gmail_modify_labels gate (system-managed only) (EMAIL-02)
- [ ] `backend/tests/compliance/email/test_compliance_router.py` — sender-domain regex covers gov.in + rbi.org.in; subject keyword match; auto-create with source=gmail; <0.75 → review queue (EMAIL-06)
- [ ] `backend/tests/compliance/email/test_bill_extraction.py` — LLM extraction with bill prompt template; regex fallback for amount + date; biller_category enum (BILL-01, BILL-02)
- [ ] `backend/tests/compliance/email/test_bill_recurrence.py` — (biller_name_normalized, account_number_last4) clustering; missing-month anomaly flag (BILL-06)
- [ ] `backend/tests/compliance/email/test_audit_pii_redaction.py` — body/subject/sender redacted; SHA-256 + IDs preserved; INFRA-06 helper invoked (EMAIL-09)
- [ ] `backend/tests/compliance/email/test_audit_immutability.py` — UPDATE/DELETE on audit_log raises (Phase 9 INFRA-07 trigger applies) (EMAIL-09)
- [ ] `backend/tests/compliance/email/test_invalid_grant_handling.py` — Gmail invalid_grant marks credential REVOKED; scanner job disabled; gmail.connection.lost event emitted (EMAIL-10)
- [ ] `backend/tests/compliance/email/test_fetch_log.py` — three-state CHECK constraint; 2× FETCH_FAILED triggers Phase 11 alert (EMAIL-07)
- [ ] `backend/tests/compliance/email/test_pii_lifecycle.py` — body never written to DB; only Python locals; assertion via grep on connection log (D-34)
- [ ] `frontend/src/components/email/__tests__/ConnectGmailButton.test.tsx` — OAuth callback handling, connected state UI
- [ ] `frontend/src/components/email/__tests__/BillDashboard.test.tsx` — Upcoming/Due Soon/Overdue/Paid filters; bulk mark-as-paid (BILL-03)
- [ ] `frontend/src/components/email/__tests__/FilterRulesEditor.test.tsx` — CRUD on gmail_filter_rules
- [ ] `frontend/src/components/email/__tests__/FetchActivity.test.tsx` — three-state log rendering
- [ ] `pyproject.toml` — add `pytest-asyncio>=0.21` for async MCP tool tests (if not present)

*Wave 0 also installs the MCP test client harness (FastMCP `Client(server_instance)` for in-memory tool invocation per researcher's recommendation in §3.1).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Gmail OAuth round-trip end-to-end | EMAIL-01 | Requires real Google account + verified OAuth client; can't be mocked end-to-end without leaking real credentials in CI | (1) Set `GOOGLE_OAUTH_CLIENT_ID` + `GOOGLE_OAUTH_CLIENT_SECRET` in `.env`; (2) docker compose up; (3) login as compliance_head; (4) navigate /dashboard/email/connect; (5) complete Google OAuth flow; (6) verify gmail_credentials row created with refresh_token_enc populated; (7) verify access_token in Redis with TTL <3600s |
| Real attachment ingestion via DMS pipeline | EMAIL-05 | Requires real Gmail message with attachment + real document_tasks Celery worker | (1) Send a test email with PDF attachment to connected Gmail; (2) Wait ≤15 min for scanner; (3) Verify documents row created with source=gmail; (4) Verify document.processing_status transitions PENDING→COMPLETED; (5) Verify Document.source_email_id set |
| BERT classifier degradation path → rule-based detector | EMAIL-06 (revised D-16) | The rule-based detector is functionally testable, but verifying the v2.1 BERT swap-in is one-file replacement requires the v2.1 work to start | (deferred to v2.1) |
| Google security assessment for production launch | EMAIL-01 | Requires Google review (4-8 weeks); not testable in code | Pre-launch checklist: submit OAuth verification at console.cloud.google.com; Testing mode supports ≤100 users with 7-day refresh tokens; Production requires assessment |
| MCP tool invocation by Phase 12 agents | EMAIL-02 | Phase 12 agents already exist but their MCP-call surface is added in Phase 15 | After Phase 15 ships: spawn a Phase 12 response-drafting agent; verify it can invoke gmail_search to find evidence emails; verify audit_log row written with action=MCP_TOOL_CALL |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s for quick command
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
