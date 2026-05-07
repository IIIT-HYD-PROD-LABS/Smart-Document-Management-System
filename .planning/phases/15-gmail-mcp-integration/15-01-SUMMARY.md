---
phase: 15-gmail-mcp-integration
plan: 01
subsystem: testing
tags: [pytest, fastmcp, gmail-api, vitest, fernet, pii, mcp, asyncio]

requires:
  - phase: 09-compliance-foundation
    provides: db_as_app_runtime / client_a / client_b parent fixtures, INFRA-06 PII helper, INFRA-07 audit immutability triggers
  - phase: 10-ml-classification-risk-scoring
    provides: review_queue_service.enqueue_low_confidence (CLASS-04 path)
  - phase: 11-alerts-and-calendar
    provides: VALID_ALERT_TYPES registry, APScheduler integration

provides:
  - 17 backend RED-state pytest stubs (41 tests) gating Plans 02-07 modules
  - 4 frontend vitest stubs gating Plan 06 React components
  - Phase 15 conftest with 8 reusable fixtures (gmail_credential_factory, mock_gmail_service, sample_compliance_email, sample_bill_email_utility, sample_spam_email, seeded_filter_rules, fernet_test_key, body_sha256)
  - PyPI version pins for fastmcp 3.2.4, google-api-python-client 2.196.0, google-auth-oauthlib 1.4.0, pytest-asyncio
  - pytest-asyncio asyncio_mode=auto wired in pyproject.toml (required by FastMCP in-memory Client tests)
  - In-memory FastMCP test harness pattern documented in test_mcp_tools.py + conftest

affects: [15-02-database, 15-03-services, 15-04-mcp-tools, 15-05-routers, 15-06-frontend, 15-07-smoke]

tech-stack:
  added:
    - fastmcp==3.2.4 (MCP server with decorator tool registration, D-29)
    - google-api-python-client==2.196.0 (official Gmail API client)
    - google-auth-oauthlib==1.4.0 (web-server OAuth flow helper)
    - pytest-asyncio>=0.21,<1.0 (async MCP tool tests)
  patterns:
    - "RED-state stub: try/except ImportError + pytest.skip(reason='Plan NN — module') keeps suite green during build"
    - "Phase-scoped conftest mirrors backend/tests/conftest.py — local fixtures inherit parent fixtures (db_as_app_runtime, client_a, client_b)"
    - "Body PII never persisted — fixtures return Gmail message JSON only as Python locals (D-34)"
    - "Deterministic Fernet key for tests via SHA-256 of stable phrase (32 raw bytes -> 44 b64 chars)"
    - "FastMCP in-memory transport documented for Phase 12 agents (Client(server_instance) — supersedes D-30 stdio + D-31 subprocess via D-38)"

key-files:
  created:
    - backend/tests/compliance/__init__.py
    - backend/tests/compliance/email/__init__.py
    - backend/tests/compliance/email/conftest.py
    - backend/tests/compliance/email/test_oauth_flow.py
    - backend/tests/compliance/email/test_credential_vault.py
    - backend/tests/compliance/email/test_scanner_dedup.py
    - backend/tests/compliance/email/test_mcp_tools.py
    - backend/tests/compliance/email/test_compliance_router.py
    - backend/tests/compliance/email/test_bill_extraction.py
    - backend/tests/compliance/email/test_bill_recurrence.py
    - backend/tests/compliance/email/test_audit_pii_redaction.py
    - backend/tests/compliance/email/test_audit_immutability.py
    - backend/tests/compliance/email/test_invalid_grant_handling.py
    - backend/tests/compliance/email/test_fetch_log.py
    - backend/tests/compliance/email/test_pii_lifecycle.py
    - backend/tests/compliance/email/test_filter_rules.py
    - backend/tests/compliance/email/test_attachment_ingestion.py
    - backend/tests/compliance/email/test_bill_dashboard.py
    - backend/tests/compliance/email/test_bill_reminders.py
    - backend/tests/compliance/email/test_bill_mark_paid.py
    - frontend/src/components/email/__tests__/ConnectGmailButton.test.tsx
    - frontend/src/components/email/__tests__/BillDashboard.test.tsx
    - frontend/src/components/email/__tests__/FilterRulesEditor.test.tsx
    - frontend/src/components/email/__tests__/FetchActivity.test.tsx
  modified:
    - backend/requirements.txt
    - backend/pyproject.toml

key-decisions:
  - "Test directory backend/tests/compliance/email/ mirrors Phase 9 module-scoped pattern (existing tests live flat under backend/tests/, but the deeper-nested layout is what the plan dictated; created intermediate compliance/__init__.py to make the package importable cleanly)"
  - "Fernet test key derived via SHA-256 of stable phrase — plan's literal urlsafe_b64encode(b'phase15-fixture-key-32-byteslong!')[:44].ljust(44, b'=') was not Fernet-valid (verified in this env: ValueError 'Fernet key must be 32 url-safe base64-encoded bytes'). Switched to base64.urlsafe_b64encode(hashlib.sha256(b'phase15-fixture-key-deterministic').digest()) — round-trip verified."
  - "Frontend stubs ship with import { describe, it } from 'vitest' even though vitest is not configured yet — Plan 06 lands the framework. describe.skip + it.todo means the imports are dead code today; not collected by any current runner."
  - "mock_gmail_service fixture guards on `import googleapiclient.discovery` and skips if the package isn't installed — matches the gmail_credential_factory pattern of skipping until Plan 02 pip-installs requirements"

patterns-established:
  - "Phase-scoped conftest pattern: backend/tests/compliance/email/conftest.py imports nothing from app.email (which doesn't exist yet); fixtures referencing Phase 15 modules use try/except ImportError + pytest.skip()"
  - "RED-state file template: file-level docstring naming REQ-IDs covered, two or more def test_* placeholders each with try/except ImportError + pytest.skip('Plan NN — module not yet implemented')"
  - "FastMCP in-memory test pattern (D-38): async with Client(mcp) as client: result = await client.call_tool(...) — documented in test_mcp_tools.py module docstring for Plan 04 to follow"
  - "Reconciliation-anchor tests: at least one test per reconciliation locks the contract (rbi.org.in in test_compliance_router.py, priority column in test_filter_rules.py, in-memory Client in test_mcp_tools.py, body never persisted in test_pii_lifecycle.py)"

requirements-completed: []  # Wave 0 lays test infrastructure only — no requirements GREEN until Plans 02-07 land modules + flip pytest.skip() to assertions

duration: 7m
completed: 2026-05-07
---

# Phase 15 Plan 01: Test Infrastructure Summary

**21 RED-state stub files (17 backend pytest + 4 frontend vitest) plus phase-scoped conftest with 8 reusable fixtures, gating every Plan 02-07 module via try/except ImportError + pytest.skip()**

## Performance

- **Duration:** ~7 min (started 2026-05-07T17:14:20Z, completed 2026-05-07T17:21:00Z)
- **Started:** 2026-05-07T17:14:20Z
- **Completed:** 2026-05-07T17:21:00Z
- **Tasks:** 3
- **Files created:** 26 (21 stubs + conftest + 2 __init__ + 2 modified)

## Accomplishments

- Wave 0 RED-state discipline established for Phase 15 (mirrors Phase 9 pattern)
- Three reconciliation locks landed in stubs: in-memory FastMCP `Client(mcp)` (recon #1, supersedes D-30/D-31 via D-38), `rbi.org.in` sender domain (recon #4), `priority` column on filter rules (open question #5)
- 41 tests collected by pytest, 0 errors, 41 clean skips — proving the import-guard pattern works against modules that do not exist yet
- PyPI pins (fastmcp 3.2.4, google-api-python-client 2.196.0, google-auth-oauthlib 1.4.0) ready for Plan 02 `pip install -r requirements.txt`
- pytest-asyncio added with `asyncio_mode = "auto"` so async MCP tool tests work without per-test markers
- 8 reusable fixtures landed: fernet_test_key, gmail_credential_factory, mock_gmail_service, sample_compliance_email, sample_bill_email_utility, sample_spam_email, seeded_filter_rules, body_sha256
- Sample email payloads use real Gmail message JSON shape (base64-encoded body, headers list, labelIds) so future bill extractor + classifier tests are realistic without mocking the API client more than once

## Task Commits

1. **Task 1: PyPI pins + pytest-asyncio config** — `f78f379` (chore)
2. **Task 2: Phase 15 conftest + 8 fixtures** — `693e716` (test)
3. **Task 3: 17 backend + 4 frontend RED stubs** — `fab035c` (test)

## Backend Test Files (17 files, 41 tests)

| # | File | Requirements | Tests |
|---|------|--------------|-------|
| 1 | test_oauth_flow.py | EMAIL-01 | 3 (consent URL, callback persistence, CSRF state) |
| 2 | test_credential_vault.py | EMAIL-03 | 2 (Fernet round-trip, access-token Redis-only) |
| 3 | test_scanner_dedup.py | EMAIL-08 | 2 (composite UNIQUE, attachment SHA-256 dedup) |
| 4 | test_mcp_tools.py | EMAIL-02, EMAIL-09 | 3 (6-tool registration, in-memory Client, audit row) |
| 5 | test_compliance_router.py | EMAIL-06 | 4 (cbic-gst, **rbi.org.in**, uncertain → review queue, forwarded → dms_only) |
| 6 | test_bill_extraction.py | BILL-01, BILL-02 | 3 (Tata Power LLM, regex fallback, biller_category enum) |
| 7 | test_bill_recurrence.py | BILL-06 | 2 (parent_bill_id linking, NULL last4 partial unique) |
| 8 | test_audit_pii_redaction.py | EMAIL-09 | 2 (body/subject/sender redacted; SHA-256 + IDs preserved) |
| 9 | test_audit_immutability.py | EMAIL-09 | 2 (UPDATE/DELETE on MCP_TOOL_CALL row raises) |
| 10 | test_invalid_grant_handling.py | EMAIL-10 | 3 (REVOKED status, scanner disable, **gmail.connection.lost** event) |
| 11 | test_fetch_log.py | EMAIL-07 | 2 (three-state CHECK, 2x FETCH_FAILED → alert) |
| 12 | test_pii_lifecycle.py | D-34 | 2 (body never in DB, body never in Redis) |
| 13 | test_filter_rules.py | EMAIL-04 | 2 (**priority** column, lower-priority wins) |
| 14 | test_attachment_ingestion.py | EMAIL-05 | 2 (Document.source_email_id FK, process_document_task triggered) |
| 15 | test_bill_dashboard.py | BILL-03 | 2 (filter buckets, bulk mark-paid atomicity) |
| 16 | test_bill_reminders.py | BILL-04 | 2 (bill_t3/bill_t1/bill_overdue alert types, max-3 cool-down) |
| 17 | test_bill_mark_paid.py | BILL-05 | 3 (payment metadata persistence, audit log, reminder cancellation) |

## Frontend Test Files (4 files)

- `frontend/src/components/email/__tests__/ConnectGmailButton.test.tsx` — EMAIL-01 OAuth handoff
- `frontend/src/components/email/__tests__/BillDashboard.test.tsx` — BILL-03 dashboard
- `frontend/src/components/email/__tests__/FilterRulesEditor.test.tsx` — EMAIL-04 CRUD
- `frontend/src/components/email/__tests__/FetchActivity.test.tsx` — EMAIL-07 three-state log

All four use `describe.skip()` + `it.todo()` (vitest config lands in Plan 06).

## Conftest Fixtures (8)

- `fernet_test_key` — deterministic 44-byte b64 key valid for `cryptography.fernet.Fernet`
- `gmail_credential_factory(user_id, client_id?, refresh_token?)` — placeholder factory; skips until Plan 02 GmailCredential ORM
- `mock_gmail_service` — patches `googleapiclient.discovery.build` returning a chainable MagicMock
- `sample_compliance_email` — realistic Gmail JSON with sender `notice@cbic-gst.gov.in`, subject `Show Cause Notice u/s 73`, body containing `GSTIN: 27AABCT1234F1ZX` and DRC-01 reference
- `sample_bill_email_utility` — Gmail JSON for Tata Power bill (sender `noreply@tatapower.com`, INR amount, due date, last-4 account)
- `sample_spam_email` — non-compliance / non-bill payload for negative classifier tests
- `seeded_filter_rules` — placeholder; skips until Plan 02 GmailFilterRule ORM
- `body_sha256` — deterministic SHA-256 hasher for D-35 audit-row body_sha256 assertions

## Files Created/Modified

### Created (24)
- `backend/tests/compliance/__init__.py` — empty package marker (intermediate dir)
- `backend/tests/compliance/email/__init__.py` — empty package marker
- `backend/tests/compliance/email/conftest.py` — 8 fixtures (161 lines)
- `backend/tests/compliance/email/test_*.py` — 17 RED-state stub files
- `frontend/src/components/email/__tests__/*.test.tsx` — 4 vitest stubs

### Modified (2)
- `backend/requirements.txt` — added 3 Phase 15 pins + pytest-asyncio
- `backend/pyproject.toml` — added `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` and `testpaths = ["tests"]`

## Decisions Made

- **Switched fernet_test_key derivation** from the plan's literal `urlsafe_b64encode(b'phase15-fixture-key-32-byteslong!')[:44].ljust(44, b'=')` to `base64.urlsafe_b64encode(hashlib.sha256(b'phase15-fixture-key-deterministic').digest())`. The literal bytes were not 32 raw bytes after b64 round-trip and Fernet rejected them with `ValueError: Fernet key must be 32 url-safe base64-encoded bytes`. SHA-256 always returns 32 bytes; the encoded form is reproducible across CI runs and accepted by `Fernet()`. Documented in conftest docstring.

- **Created intermediate `backend/tests/compliance/__init__.py`** because the existing project ships its tests flat under `backend/tests/test_*.py`, with no `compliance/` subdirectory. The plan specified `backend/tests/compliance/email/` so I built that hierarchy and added an empty `__init__.py` at the `compliance/` level to keep the package importable. No existing tests broke (pytest discovers the flat tests by file pattern, not package).

- **Added `[tool.pytest.ini_options]` block to pyproject.toml** rather than reusing an existing one — the existing `pyproject.toml` was minimal (uv config only). The new block sets `asyncio_mode = "auto"` (required for async MCP tool tests) and `testpaths = ["tests"]` so `cd backend && pytest` finds the suite.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Fernet test key encoding was invalid**

- **Found during:** Task 2 (conftest creation)
- **Issue:** The plan specified `base64.urlsafe_b64encode(b"phase15-fixture-key-32-byteslong!")[:44].ljust(44, b"=")` for the fernet_test_key fixture. Verified with `python3 -c "from cryptography.fernet import Fernet; ..."` that this raises `ValueError: Fernet key must be 32 url-safe base64-encoded bytes` because the input phrase is 33 bytes and the slice/pad produces a 44-byte string that does not decode back to 32 raw bytes.
- **Fix:** Switched to `base64.urlsafe_b64encode(hashlib.sha256(b"phase15-fixture-key-deterministic").digest())` — SHA-256 always emits 32 bytes; the encoded form is 44 b64 chars; `Fernet()` accepts it; round-trip `f.encrypt(b'hello')` / `f.decrypt(...)` verified.
- **Files modified:** `backend/tests/compliance/email/conftest.py` (lines 22-31, fixture body and docstring)
- **Verification:** `python3 -c "import base64, hashlib; from cryptography.fernet import Fernet; key = base64.urlsafe_b64encode(hashlib.sha256(b'phase15-fixture-key-deterministic').digest()); f = Fernet(key); blob = f.encrypt(b'hello'); print(f.decrypt(blob))"` → `b'hello'`
- **Committed in:** `693e716` (Task 2 commit)

**2. [Rule 3 — Blocking] Created intermediate `backend/tests/compliance/__init__.py`**

- **Found during:** Task 2 (directory setup)
- **Issue:** The plan assumed `backend/tests/compliance/` existed. It did not — all existing compliance tests live flat under `backend/tests/test_*.py`. Adding `backend/tests/compliance/email/conftest.py` without `backend/tests/compliance/__init__.py` would have left an awkward gap.
- **Fix:** Wrote empty `backend/tests/compliance/__init__.py` to mark the intermediate dir as a package.
- **Files modified:** `backend/tests/compliance/__init__.py` (new, 0 bytes)
- **Verification:** `pytest tests/compliance/email/ --collect-only` → 41 collected, 0 errors. Existing flat tests still discovered (file-pattern, not package-based).
- **Committed in:** `693e716` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both auto-fixes essential for correctness — without them the conftest imports would fail and the directory layout would be incomplete. No scope creep; all tests still RED-state stubs.

## Issues Encountered

None substantive. Two minor warnings during pytest:

- `PytestConfigWarning: Unknown config option: asyncio_mode` — expected; pytest-asyncio is in `requirements.txt` but not yet installed in the local venv. Plan 02 `pip install -r requirements.txt` resolves it. The warning does not block test collection.

## User Setup Required

None — no external service configuration in this plan.

## Next Phase Readiness

- **Plan 02 (Wave 1)** can immediately consume these fixtures and convert pytest.skip() to assertions: `app.email.models.{credential, message_log, fetch_log, filter_rule, bill}` referenced from 7+ test files; running `pip install -r requirements.txt` brings in fastmcp + google-api-python-client + pytest-asyncio so MCP and async tests actually execute.
- **Plan 03 (Wave 2)** lands `app.email.services.{oauth_service, credential_vault, classifier, bill_extractor, scanner_service, bill_service, ingestion_service}` referenced by 12 test files — the import-guard pattern flips skip → assertion as each module ships.
- **Plan 04 (Wave 3)** lands `app.email.mcp.{server, tools}` and `gmail_search_impl` etc. — test_mcp_tools, test_audit_pii_redaction, test_audit_immutability, test_attachment_ingestion all start asserting once Plan 04 commits land.
- **Plan 06 (Wave 5)** lands vitest config + the 4 React components; the frontend stubs flip `describe.skip` → `describe`.
- **Reconciliation contracts locked:** in-memory `Client(mcp)` (D-38), rbi.org.in sender (recon #4), priority column on GmailFilterRule (open Q #5), body-never-persisted (D-34), gmail.connection.lost event (EMAIL-10).

---

*Phase: 15-gmail-mcp-integration*
*Plan: 01 — Test Infrastructure (Wave 0)*
*Completed: 2026-05-07*

## Self-Check: PASSED

All 24 created files exist on disk. All 3 task commits exist in git history (`f78f379`, `693e716`, `fab035c`). Both modified files (`backend/requirements.txt`, `backend/pyproject.toml`) carry the required additions (3 PyPI pins, asyncio_mode setting). `cd backend && pytest tests/compliance/email/ -x` returns `41 skipped, 0 failed, 0 errors`.
