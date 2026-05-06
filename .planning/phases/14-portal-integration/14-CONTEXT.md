# Phase 14: Government Portal Integration - Context

**Gathered:** 2026-05-05 (seed scope; awaiting `/gsd:discuss-phase 14`)
**Status:** CONTEXT seeded — heavily blocked on external credential / API access

<domain>
## Phase Boundary

**In scope:** Notices from GST, Income Tax, MCA portals are auto-fetched
on schedule. RBI/SEBI public enforcement notices are scraped. Non-Gmail
email inboxes are parsed via IMAP. All with encrypted credential storage,
fetch health monitoring, and duplicate prevention.

**Specifically:**
1. GST portal API integration (GSTIN-based) via GSP empanelment OR direct
   GST API access (developer.gst.gov.in)
2. Income Tax e-filing portal integration (PAN-based) — TBD whether public
   API exists or if scraping is the only path
3. MCA portal integration (CIN-based)
4. RBI public enforcement notices scraper (rbi.org.in)
5. SEBI public enforcement orders scraper (sebi.gov.in/enforcement/orders)
6. Generic IMAP parsing for Outlook/Yahoo/custom email accounts (Gmail
   is Phase 15)
7. Encrypted credential vault (Fernet, INFRA-06 reused)
8. PortalFetchLog with three-state result (SUCCESS_EMPTY /
   SUCCESS_WITH_RESULTS / FETCH_FAILED)
9. Duplicate prevention via UNIQUE constraint + Redis distributed lock
10. Admin alert on 2× consecutive FETCH_FAILED runs

**Out of scope:**
- Outbound submissions to portals — Phase 12 owns response drafting; v3.0 may auto-submit
- Bank statement portals (HDFC, ICICI APIs) — defer indefinitely
- State-tax portals (PT, VAT) — v2.1+
- Real-time webhook ingestion from portals — most portals don't support; polling is the contract

</domain>

<decisions>
## Proposed Decisions (refine via `/gsd:discuss-phase 14`)

### Portal API access (PORT-01..03)
- **D-01:** GST portal — empanel as GSP at developer.gst.gov.in OR use
  third-party aggregator (Cygnet, ClearTax, TaxBuddy) that already
  maintains API access. Empanelment takes 2-3 weeks; aggregator costs ~₹5K/month.
- **D-02:** Income Tax — no public API for individual notices. Strategy: scrape e-filing portal post-login using session cookies + CAPTCHA-solving service, OR use the e-Proceedings PDF download path that doesn't require CAPTCHA after the first login.
- **D-03:** MCA — public CIN search returns metadata only; SCN under §454 are emailed individually. Plan B: parse the email account that received the SCN (via IMAP).

### Scraping (PORT-04)
- **D-04:** RBI + SEBI scrapers in `backend/app/compliance/portals/scrapers/`
  using `requests` + `beautifulsoup4` (already in requirements.txt). Run
  on cron via APScheduler (Phase 11 dependency).
- **D-05:** Robots.txt compliance + per-domain rate limit (1 req/sec
  default). User-Agent identifies us as a compliance-aggregation tool.

### IMAP integration (PORT-05)
- **D-06:** `imaplib` (stdlib) + `email.parser` for standard mail accounts.
  Per-credential cadence configurable (default 15 min).
- **D-07:** Attachment extraction for known compliance senders (`@gst.gov.in`,
  `@incometax.gov.in`) — auto-route to ComplianceNotice creation; other
  senders skipped to avoid noise.

### Credential vault (INFRA-06)
- **D-08:** `portal_credentials` table with Fernet-encrypted columns:
  `username_enc`, `password_enc`, `api_key_enc`, `imap_host`, `imap_port`,
  `imap_use_ssl`. Key management via existing Phase 9 INFRA-06 PII helper.
- **D-09:** No credential ever in Celery task arguments, log lines, or
  Elasticsearch source fields. Decryption happens inside the worker
  process, used immediately, never persisted in plaintext.

### Fetch health (PORT-06)
- **D-10:** `portal_fetch_log` table with (portal, credential_id, started_at,
  completed_at, result, item_count, error). Three-state result encoded as
  CHECK constraint.
- **D-11:** Alert pipeline (Phase 11) consumes `portal_fetch_log` rows;
  2× consecutive FETCH_FAILED triggers admin alert via SendGrid (or Resend) channel.

### Duplicate prevention (PORT-08)
- **D-12:** UNIQUE constraint on `compliance_notices.notice_number` per
  client. Redis distributed lock (`SET nx ex`) keyed on `(portal, credential_id)`
  prevents two pollers running simultaneously for the same credential.

### Frontend (UI hint: yes)
- **D-13:** `/dashboard/compliance/portals` page — connection status per
  authority, last-fetch timestamp, error log link. Admin-only.

</decisions>

<canonical_refs>
- `backend/app/compliance/utils/pii_encryption.py` — Fernet helper from Phase 9 INFRA-06
- `backend/app/ml/datasets/scrape_sebi.py` — existing SEBI scraper pattern (Phase 10 dataset prep)
- `backend/app/compliance/services/scheduler.py` — APScheduler integration (Phase 11)
- `backend/app/tasks/celery_app.py` — Celery routing
- `.planning/REQUIREMENTS.md` — PORT-01..08
</canonical_refs>

<deferred>
- Outbound portal submissions — Phase 12+ rather than Phase 14 (response drafting owns the verb)
- Real-time webhook ingestion — most government portals don't expose webhooks
- State VAT / Professional Tax portals — v2.1+
- Bank statement aggregation — out of scope
</deferred>

## Open Blockers (must resolve before /gsd:plan-phase 14)
1. **GST GSP empanelment status** — has the org applied? Is empanelment
   feasible in v2.0 timeline? If not, third-party aggregator route adds
   recurring cost. Decision must come from product/business owner.
2. **Income Tax e-filing API access** — public API does not exist as of
   2026-05. Choose: (a) scrape with session cookies + CAPTCHA solver, (b)
   GST aggregator that bundles IT, (c) defer IT auto-fetch to v3.0.
3. **MCA portal API** — same as IT; defer or accept email-based ingestion path.
4. **RBI/SEBI scraping legal review** — robots.txt compliance + ToS — LegalOps sign-off needed.
5. **Credential storage policy** — passwords in Fernet vault is technically
   sound; compliance team needs sign-off on storing portal passwords at all (some clients prefer to enter manually).

**Recommendation: Phase 14 cannot proceed past `/gsd:plan-phase 14` until
items 1-2 above are resolved. v2.0 may ship without Phase 14 in the milestone
if access negotiation extends past launch — RBI + SEBI scrapers + IMAP
integration ship as a Phase 14a slice while GST/IT/MCA ship as 14b.**
