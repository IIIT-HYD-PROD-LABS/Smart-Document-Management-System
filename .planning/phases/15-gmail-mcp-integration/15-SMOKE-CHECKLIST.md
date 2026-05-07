# Phase 15 Manual Smoke Checklist

Manual end-to-end verification before production launch. Automated coverage lives in `scripts/smoke_phase15_v20.py` (12 checks); this document covers the parts that require a real Gmail account or human eyes.

## Pre-flight

- [ ] **Google Cloud Console:** OAuth client (Web application) registered. Authorized redirect URI `${BASE_URL}/api/email/gmail/oauth/callback` added (matches `GMAIL_OAUTH_REDIRECT_URI`).
- [ ] **Backend `.env`:** `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GMAIL_OAUTH_REDIRECT_URI`, `FERNET_KEY`, `REDIS_URL`, `DATABASE_URL`, `DATABASE_URL_RUNTIME` all set.
- [ ] **Vercel + Render dashboards:** the same env vars set in deployment configuration.
- [ ] **`docker compose up -d`** brings all 6 services healthy (per project memory: Smart-Docs runs via docker-compose only).
- [ ] **`cd backend && alembic upgrade head`** reports head at or beyond `0026_apscheduler_jobs_table` (Phase 15 migrations applied).
- [ ] **Login** with a `compliance_head` account that has an active `client_membership`.

## End-to-end smoke (12 steps)

1. **Login + navigate to `/dashboard/email/connect`.**
   - [ ] "Connect Gmail" button visible (no existing credential).
   - [ ] Sidebar shows the Email section between Documents and Compliance with Connect / Settings / Activity / Bills sub-links.

2. **Click Connect Gmail.**
   - [ ] Browser redirects to `accounts.google.com` consent screen.
   - [ ] Consent screen shows requested scopes: `gmail.readonly`, `gmail.modify`.
   - [ ] After consent, browser redirects back to `/dashboard/email/connect?status=success&credential_id=N`.
   - [ ] Page now shows "Connected to {email}" with cadence info.
   - [ ] DB check: `SELECT id, status, refresh_token_enc, last_history_id FROM gmail_credentials WHERE id = N;` — `status='active'`, `refresh_token_enc IS NOT NULL` (BYTEA), `last_history_id` NULL initially.
   - [ ] Redis check: `redis-cli GET gmail:access:{N}` — access token cached with TTL <3600s. **EMAIL-03**: refresh token never cached in Redis; only access token.

3. **Filter rules CRUD on `/dashboard/email/settings`.**
   - [ ] FilterRulesEditor renders.
   - [ ] Click "+ Add Rule". A new row appears with `priority=100`, `route_to=ignore`.
   - [ ] Edit `sender_pattern` to `@your-test-bill-address`, `route_to` to `bill`. Click outside to save. Toast: "Saved".
   - [ ] DB check: `SELECT priority, sender_pattern, route_to FROM gmail_filter_rules WHERE credential_id = N ORDER BY priority ASC;` — rows ordered by priority ASC (open question #5: lower wins).
   - [ ] Delete the rule via Delete button. Confirm prompt. Row removed.

4. **Real attachment ingestion (EMAIL-05).**
   - [ ] Send a test email with a small PDF attachment to the connected Gmail address. Use a sender that matches an existing filter rule, OR add a temporary rule for `your-test-sender@*` → `dms_only` (so the message is ingested as a Document without auto-creating a notice).
   - [ ] Wait up to `cred.cadence_minutes` (default 15min) OR trigger manually:
         `docker compose exec backend python -c "from app.email.tasks.scanner_task import run_scan; run_scan({N})"`
   - [ ] DB check: `SELECT id, route_taken, sender_domain FROM gmail_message_log WHERE credential_id = N ORDER BY processed_at DESC LIMIT 1;` — row exists.
   - [ ] DB check: `SELECT id, source_email_id, status FROM documents WHERE source_email_id IS NOT NULL ORDER BY id DESC LIMIT 1;` — Document row created with `source_email_id` set; status transitions PENDING → COMPLETED via Celery worker.

5. **Bill detection (BILL-01, BILL-02).**
   - [ ] Send (or have on hand) a sample utility/telecom bill email — e.g., a Tata Power bill from `noreply@tatapower.com`, or your real biller. Subject line should mention amount + due date.
   - [ ] After scanner runs (manual trigger if needed): `SELECT id, biller_name, biller_category, amount_due, due_date, account_number_last4 FROM bills ORDER BY id DESC LIMIT 1;` — row created with non-null amount_due + due_date.
   - [ ] Visit `/dashboard/email/bills`. Stat card "Upcoming" or "Due Soon" increments accordingly.

6. **View source email button (D-18, D-37).**
   - [ ] Click on the bill in `/dashboard/email/bills`. Detail page `/dashboard/email/bills/[id]` loads.
   - [ ] Click the "View source email" button.
   - [ ] Email body renders inline as `<pre>` (max-h-96 overflow-auto).
   - [ ] DB check: `SELECT created_at, action, target FROM audit_logs WHERE action = 'MCP_TOOL_CALL' AND target = 'gmail_read_message' ORDER BY created_at DESC LIMIT 1;` — row written by the MCP tool itself.
   - [ ] Audit details JSON contains `body_sha256` and message_id but NOT `body`, `sender`, or `subject` (D-36 PII redaction).
   - [ ] Reload the page. Body is NOT cached client-side — the button must be clicked again to re-fetch (D-34 PII lifecycle).

7. **Mark as paid (BILL-05).**
   - [ ] Click "Mark as Paid" button on bill detail page. Modal opens.
   - [ ] Enter `payment_date=today`, `reference=TEST-001`, `method=upi`. Submit.
   - [ ] Toast "Marked paid". Page reloads. Status changes to Paid.
   - [ ] DB check: `SELECT payment_status, payment_date, payment_reference, payment_method FROM bills WHERE id = ?;` — `payment_status=paid`, fields populated.
   - [ ] DB check: `SELECT created_at, action FROM audit_logs WHERE action = 'BILL_MARK_PAID' ORDER BY created_at DESC LIMIT 1;` — row written.
   - [ ] APScheduler check: `psql -c "SELECT id FROM apscheduler_jobs WHERE id LIKE 'gmail_bill_reminder_${BILL_ID}%';"` — 0 rows (D-22: marking paid cancels all 3 reminder jobs).

8. **Connection-lost banner (EMAIL-10).**
   - [ ] Open `myaccount.google.com/permissions`. Revoke access to your Smart-Docs OAuth app.
   - [ ] Trigger a scan: `docker compose exec backend python -c "from app.email.tasks.scanner_task import run_scan; run_scan({N})"`.
   - [ ] DB check: `SELECT status FROM gmail_credentials WHERE id = N;` — `status='revoked'`.
   - [ ] DB check: `SELECT status FROM gmail_fetch_log WHERE credential_id = N ORDER BY started_at DESC LIMIT 1;` — `FETCH_FAILED` (or similar terminal status — exact name depends on revocation timing).
   - [ ] Visit `/dashboard/email/connect`. Red "Reconnect required" banner shown with amber Reconnect CTA.
   - [ ] APScheduler: `gmail_scan_{N}` job removed.

9. **Bulk mark-paid (BILL-03, BILL-06).**
   - [ ] Reconnect Gmail (step 2 again — `prompt=consent` will issue a new refresh token).
   - [ ] Wait for or simulate at least 2 bill rows (re-run the test bill flow in step 5 with different billers).
   - [ ] On `/dashboard/email/bills`, check 2 bills via the row checkboxes.
   - [ ] Selection toolbar slides in. Click "Bulk mark paid". Modal opens.
   - [ ] All checked bills move to Paid status; counts update. Toast shows `ok=N, failed=0`.
   - [ ] DB check: per-row `BILL_MARK_PAID` audit rows written for each bill (Plan 05 per-row SAVEPOINT semantics: a single failure does not roll back the whole batch).

10. **Phase 12 agent integration (DEFERRED — Phase 12 v2.1 only).**
    - [ ] Skip in v2.0 launch. Phase 12 v2.1 work adds the agent surface; this checklist item activates then.
    - [ ] Pre-launch sanity: `docker compose exec backend python -c "import asyncio; from app.email.mcp.client import call_gmail_tool; print(asyncio.run(call_gmail_tool('gmail_search', {'user_id': 1, 'client_id': 1, 'query': 'newer_than:7d'})))"` — returns a dict with `message_ids` (or a clean ToolError if creds missing). Verifies the in-memory FastMCP transport (D-38, recon #1) works.

11. **Google OAuth verification (Pitfall 4 — production launch dependency).**
    - [ ] Submit OAuth verification request at `console.cloud.google.com` for restricted scopes (`gmail.readonly`, `gmail.modify`). Process takes 4–8 weeks.
    - [ ] Until verified, the app operates in Testing mode: max 100 users, refresh tokens expire after 7 days.
    - [ ] For pilot launch, document this constraint in user-facing release notes.

12. **Audit log PII redaction verification (D-36, EMAIL-09).**
    - [ ] `SELECT details FROM audit_logs WHERE action = 'MCP_TOOL_CALL' ORDER BY created_at DESC LIMIT 5;`
    - [ ] Inspect each row's JSON. Confirm details contain: tool name, client_id, body_sha256 (or query_sha256), message_id, attachment_ids[].
    - [ ] Confirm details do NOT contain: body content, sender email full address, subject text, attachment bytes, raw query text (only `query_sha256`).
    - [ ] Confirm immutability: `UPDATE audit_logs SET action='X' WHERE id=?;` raises an `append-only` error (Phase 9 INFRA-07 trigger). Same for `DELETE`.

## Sign-off

- [ ] All 12 steps GREEN (10 + 12 mandatory; 10 deferred to Phase 12 v2.1, 11 deferred 4–8 weeks for OAuth verification).
- [ ] Automated smoke (`docker compose exec backend python /app/../scripts/smoke_phase15_v20.py`) GREEN — all 12 named checks PASS.
- [ ] No regressions in existing test suite: `docker compose exec backend pytest tests/ -x --tb=short`.
- [ ] Phase 15 SHIPPED v2.0.
