# Phase 1-13 Second Hardening Pass — 2026-05-05

Source: 5-agent end-to-end audit (code-reviewer, security-auditor, debugger,
silent-failure-hunter, gsd-integration-checker) covering ALL phases 1-13.
50+ raw findings deduplicated into 25 distinct issues. This plan is the
audit trail of which items are fixed in this session and which are deferred.

The first hardening pass (`HARDENING-PLAN.md`) covered Phases 9-11. This
second pass extends to Phases 12 + 13 plus catches v1.0 regressions
introduced by v2.0 changes — including a SCHEDULER REGRESSION of the
first-pass tenant-context fix.

---

## Block-now (Tier A — 5 CRITICAL)

### CRIT-1. Documents cross-user leak via unified search
**Source:** debugger Iss1 + code-reviewer C-1 + integration-checker Flow 3
**File:** `backend/app/compliance/services/unified_search_service.py:102-125`
**Why critical:** `documents` table has no compliance RLS; the unified
search SQL has zero `user_id`/`client_id` filter on the documents leg.
Any authenticated compliance user can search every user's private
documents in the system.
**Fix:** Pass `user_id` from the router; SQL adds
`AND (d.user_id = :user_id OR EXISTS document_permissions row)`. Update
docstring's false RLS claim.

### CRIT-2. APScheduler RLS regression
**Source:** code-reviewer C-2 (NEW; no other agent caught it)
**File:** `backend/app/compliance/services/scheduler.py:122-166`
**Why critical:** `_dispatch_scheduled_alert` opens `SessionLocal()` with
no tenant context. RLS fail-closed → `db.get(ComplianceNotice)` returns
None → every T-7/T-3/T-1/overdue alert silently no-ops in production.
This is a REGRESSION of the first-pass hardening fix #1 which patched
the Celery tasks but missed the APScheduler path.
**Fix:** Add `set_tenant_context_for_celery(client_id=None, user_id=None,
cross_mode=True)` then narrow on `notice.client_id` after load — exact
mirror of `app/tasks/alert_tasks.py:54-65`.

### CRIT-3. Audit failure fallback path is ephemeral
**Source:** silent F1 + code-reviewer H-2
**File:** `backend/app/services/audit_service.py:30-32` +
`docker-compose.yml`
**Why critical:** First-pass hardening #3 added a JSONL dead-letter at
`/tmp/audit_failures.jsonl`. `/tmp` is wiped on every container restart.
The regulatory dead-letter is itself ephemeral.
**Fix:** Default path moves to `/data/audit_failures/audit_failures.jsonl`;
docker-compose mounts a named volume for `/data/audit_failures`; startup
warning if `AUDIT_FAILURES_PATH` resolves under `/tmp/`.

### CRIT-4. Audit write failures swallowed by callers
**Source:** silent F2
**File:** `backend/app/compliance/services/response_service.py` +
`backend/app/compliance/services/evidence_service.py`
**Why critical:** `log_audit_event` returns False on DB failure (per
the first-pass fix). Callers ignore the bool. Approval/state-change
rows commit successfully, user sees 200 OK, but the regulatory trail
doesn't exist.
**Fix:** Service callers check the return; on False, surface a warning
log line with structured fields tagged for an ops alert. The response
is still 200 (user shouldn't get a 500 because of audit issues — that's
the original contract) but the dead-letter file gets the row.

### CRIT-5. LLM regex fallback masquerades as completed AI extraction
**Source:** silent F3
**File:** `backend/app/services/llm_service.py:255-271` +
`backend/app/tasks/document_tasks.py:138-143`
**Why critical:** When ALL real LLM providers fail (Anthropic + Gemini +
OpenAI + Ollama), the chain falls through to `LocalProvider` (regex stub)
and returns `provider="local"`. Caller marks
`ai_extraction_status="completed"`. Users believe AI extraction occurred
when only regex ran — a serious accuracy claim violation in compliance
contexts.
**Fix:** `extract_with_llm` returns a tuple `(result, degraded: bool)`
where degraded=True means "all real providers failed; result came from
the local stub". Caller persists `ai_extraction_status="degraded_local"`
distinctly from `completed`.

---

## Block-now (Tier B — high-impact HIGH)

### H-A. NOTICE_VIEW gate on `/approve` + `/reject` is too weak
**Source:** security C-1 + code-reviewer H-1
**File:** `backend/app/compliance/routers/responses.py:404-447`
**Fix:** Inline the per-stage permission check as a dependency that runs
BEFORE the handler body. New helper `require_any_compliance_permission`
admits any of NOTICE_APPROVE / NOTICE_APPROVE_LEGAL / NOTICE_APPROVE_CFO,
then `_decide` enforces the precise stage match.

### H-B. `_get_notice` no `client_id` filter (defense in depth)
**Source:** security H-1
**File:** `backend/app/compliance/routers/responses.py:81-92`
**Fix:** Pass `membership` into `_get_notice`, add
`.filter(ComplianceNotice.client_id == membership.client_id)`.
Mirrors `routers/notices.py` pattern.

### H-C. Evidence attach no document ownership check
**Source:** debugger Iss9 + silent F5
**File:** `backend/app/compliance/services/evidence_service.py:33`
**Fix:** Verify document is accessible to the current user — either
`document.user_id == user_id` OR a `DocumentPermission` row grants
access. Add 403 path.

### H-D. TOCTOU on `is_response_approved`
**Source:** debugger Iss3
**File:** `backend/app/compliance/services/notice_service.py:86`
**Fix:** Inside `transition_notice_status`, when checking SUBMITTED gate,
fetch the response with `.with_for_update()` so the response can't change
between the check and the notice UPDATE commit.

### H-E. `cancel_deadline_alerts` bare except (regression of fix note)
**Source:** silent F7
**File:** `backend/app/compliance/services/scheduler.py:117-118`
**Fix:** Narrow to `apscheduler.jobstores.base.JobLookupError`.

### H-F. WebSocket recheck only fires on idle clients
**Source:** integration-checker Flow 4
**File:** `backend/app/compliance/routers/notifications.py:113-144`
**Fix:** Track `last_recheck_at`; on every receive_text branch, if
elapsed since last recheck > `MEMBERSHIP_RECHECK_SECONDS`, do the
membership/JWT check. Busy clients no longer evade.

### H-G. WebSocket broadcast lacks server-side recipient filter
**Source:** integration-checker Flow 1
**Files:** `senders.py` + `manager.py`
**Fix:** Verify `senders.WebSocketSender` always includes
`recipient_user_id` in the published envelope. The manager already
filters on it but only if the field is present.

### H-H. SmsSender no `\r\n` strip
**Source:** security H-2
**File:** `backend/app/compliance/services/senders.py:145-151`
**Fix:** Strip `\r` and `\n` from interpolated fields. Same defensive
pattern as `_subject_for`.

### H-I. Past-deadline silent drop
**Source:** integration-checker Flow 1
**File:** `backend/app/compliance/services/scheduler.py:69-91`
**Fix:** When all T-7/T-3/T-1 are `in_past`, schedule the `overdue`
job for `now + 5 min` instead of `deadline + 1 day` (which is also in
the past).

### H-J. Calendar/scheduler don't apply `adjust_deadline`
**Source:** integration-checker Flow 5
**Files:** `seed.py`, `scheduler.py`, `routers/calendar.py`
**Fix:** Apply `adjust_deadline` in `seed_year` (so the seeded
RegulatoryCalendar entries reflect the adjusted date when the original
falls on a Sunday/holiday). The Phase 11 calendar UI legend then matches
reality. Scheduler integration is a v2.1 follow-up since it requires
state_code per client (currently not modeled).

### H-K. `client.name` interpolated unescaped into `summary_html`
**Source:** security M-1
**File:** `backend/app/compliance/services/report_service.py:96-108`
**Fix:** `html.escape()` on `client.name` and `month` before interpolation.

---

## Deferred (Tier C/D — v2.0.1 / v2.1 backlog)

The remaining ~14 findings are deferred. Rationale:

- **OAuth JWT in URL** (security H-3): Token-ticket pattern requires
  Redis schema design + frontend changes. Real fix, but non-trivial; v2.0.1.
- **Search router no exception handling** (silent F4): Production hardening,
  not a security issue. v2.0.1.
- **Evidence attach IntegrityError race** (silent F5): TOCTOU produces 500
  rarely; defense-in-depth fix. v2.0.1.
- **document_tasks AI status mislabeling** (silent F8): Subset of CRIT-5;
  the ai_extraction_status tristate change handles this. Verify the change
  propagates to the document page surface; if not, v2.0.1 frontend follow-up.
- **ILIKE leading-wildcard perf** (code-reviewer H-4): Performance, not
  correctness. v2.1.
- **Multi-worker APScheduler enforcement** (code-reviewer M-4): Operational
  guard rail; v2.1 with Redis distributed lock.
- **Cross-client mode non-determinism** (security M-2): Permission ordering
  fix; v2.1.
- **WebSocket JWT in query string** (security M-3): Architectural; depends
  on browser WebSocket header constraints. v2.1 ticket-pattern.
- **response_service activity-after-commit atomicity** (code-reviewer M-2):
  Refactor; same-transaction activity write would touch every service
  method. v2.0.1.
- **`extract('month', ...)` index-blind** (code-reviewer M-3): Perf; v2.1
  rewrite to date-range filters.
- **`response_drafted` doesn't cancel deadline alerts** (integration-checker
  Flow 2): Behavioral; the current behavior is arguably correct (deadline
  reminders should fire while drafting if not yet submitted). v2.0.1
  product decision.
- **stripHtml regex naive** (code-reviewer M-5): React text rendering
  protects today; v2.1 DOMPurify if highlighting restored.
- **search_vector trigger doesn't repopulate on direct NULL set**
  (code-reviewer M-7): Ops contract; document, don't change.
- **Sidebar exposes compliance items to viewers without membership**
  (code-reviewer L-4): UX polish; v2.0.1.

---

## Verification gates after this pass

1. All 5 CRITICAL items committed
2. All 11 Tier B items committed (excluding H-G which is verify-then-fix)
3. Existing 161 tests still GREEN
4. ≥ 6 new tests covering the new contracts (NOTICE_VIEW gate replacement,
   client_id filter, document ownership in evidence attach, TOCTOU FOR UPDATE,
   degraded-local LLM, audit dead-letter durability)
5. Phase 10 + Phase 12 + Phase 13 smokes still PASSED
6. New Phase 13 smoke variant: search as user A, verify user B's documents
   are NOT in results (regression test for CRIT-1)
