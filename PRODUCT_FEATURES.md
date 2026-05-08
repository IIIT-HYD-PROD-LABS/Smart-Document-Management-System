# TaxSync — Product Features Overview

**Version:** v2.0.1 (May 2026 release)
**Date:** 8 May 2026
**Audience:** Stakeholders, CA firm partners, product owners, and team leads
**Prepared for:** IIIT Hyderabad Product Labs and CA firm clients

---

## Executive Summary

TaxSync is a smart document and compliance platform built for Indian tax practitioners, CA firms, finance teams, and individuals managing regulatory paperwork. It combines an intelligent document library with end-to-end compliance notice management — from intake (manual upload or automatic Gmail capture), through classification and risk scoring, to drafting, approval, and tracking.

The platform is currently shipping its v2.0 release. The core document management product is mature and in everyday use; the compliance management layer (notices, deadlines, alerts, approval workflows, Gmail-driven intake, household bill tracking) is feature-complete except for one block of work that depends on government portal access still being negotiated. This document lists every feature available today, explains how to use each one in plain language, and shows what is on the roadmap next.

---

## How to Read This Document

Each feature has a status pill:

- **Available** — live in the product right now, you can use it today
- **In Progress** — partially shipped, broader rollout next release
- **Planned** — committed to a future release with an estimated window
- **Blocked** — depends on an external decision (regulator, government portal access)

Features are grouped by user need (what you want to do), not by internal release waves.

---

## A. Document Management

Upload, organise, find, share, and track every document — invoices, contracts, bank statements, tax papers, insurance, real estate.

### A1. Upload Any Document — **Available**

Drag and drop or browse to upload PDF, Word, JPEG, PNG, or TIFF files up to 16 MB. The system handles single uploads or batches.

**How to use it:**
1. Click the upload button on the Documents page.
2. Drag your file into the upload area, or click to browse.
3. Wait a few seconds — you will see processing progress.
4. Once complete, the document appears in your library with category, summary, and key fields filled in.

### A2. Automatic Text Reading from Scans and PDFs — **Available**

Even if your document is a phone-camera photograph or scanned image, TaxSync reads the text inside, including blurred or skewed scans. PDFs with embedded text are read directly. The result is searchable, indexable text.

**How to use it:**
1. Upload your document — no extra setting required.
2. Open the document detail page.
3. View the extracted text in the preview pane.
4. Search the full text using the search bar.

### A3. Auto-Categorisation into 7 Document Types — **Available**

Documents are automatically sorted into Invoices, Tax, Bank, Bills, Insurance, Real Estate, and Other. This works with about 85% accuracy and can be corrected manually if needed.

**How to use it:**
1. Upload any document.
2. Open the document — note the auto-assigned category badge.
3. If the category is wrong, click "Edit" and select the correct one.
4. Filter your library by category from the sidebar.

### A4. Smart Extraction of Vendor, Date, and Amount — **Available**

The system pulls out structured data from your documents: vendor or party names, dates, amounts, account numbers. You can see these in the document detail page without having to read the full file.

**How to use it:**
1. Open any uploaded document.
2. View the "Key Fields" panel on the right.
3. Edit any field if the extraction is imperfect.
4. Use these fields to filter, sort, or report.

### A5. AI-Generated Document Summaries — **Available**

Every document gets a short, plain-English summary so you can scan a stack of documents in seconds without opening each one.

**How to use it:**
1. Upload a document.
2. Wait a moment for the summary to generate.
3. Read the summary on the document card or detail page.

### A6. Document Sharing with Roles — **Available**

Share any document with a teammate as Viewer (read-only), Editor (can update), or Admin (full control). Permissions are enforced strictly across the platform.

**How to use it:**
1. Open any document.
2. Click "Share".
3. Enter the teammate's email and choose a role.
4. They get access immediately when they sign in.

### A7. Version Control with Rollback — **Available**

Every change to a document is stored as a new version. You can see version history and restore an earlier copy at any time.

**How to use it:**
1. Open a document.
2. Click the "Versions" tab.
3. Pick the version you want.
4. Click "Restore" to make it the current version.

### A8. Document Preview in Browser — **Available**

Open any PDF or image directly in the browser without downloading. Page navigation, zoom, and print controls are built in.

**How to use it:**
1. Click any document tile.
2. The preview opens in your browser.
3. Use page controls to navigate or download a copy if needed.

### A9. Full-Text Search Across the Library — **Available**

Search across the contents of every document — not just file names. Typos are forgiven (fuzzy matching). Filter further by category, date range, amount, or vendor.

**How to use it:**
1. Type anything into the search bar at the top of the Documents page.
2. Add filters from the sidebar (date range, category, amount).
3. Click any matching result to open it.

### A10. Document Analytics Dashboard — **Available**

See how your library is growing over time, which categories you have most of, and recent uploads at a glance.

**How to use it:**
1. Click "Analytics" in the sidebar.
2. View document count, monthly uploads, and category breakdown.
3. Hover charts for exact numbers.

---

## B. Compliance Notice Management

End-to-end tracking of regulatory notices from GST, Income Tax, MCA, RBI, and SEBI — built for CA firms managing many clients.

### B1. Multi-Client Tracking — **Available**

CA firms and consultants can manage many client entities, each with its own GSTIN, PAN, or CIN. Switch between clients with one click. Senior roles (Compliance Head, CA Consultant, CFO) can also see a combined cross-client view.

**How to use it:**
1. From the top bar, open the client switcher.
2. Pick a specific client — the dashboard refilters instantly.
3. Or pick "All Clients" to see a combined view (senior roles only).
4. Add new clients via the onboarding wizard from the Clients page.

### B2. Compliance Notice Intake — **Available**

Add a new notice three ways: drag-and-drop a PDF/JPG/PNG, fill in metadata manually, or let the Gmail integration capture it automatically.

**How to use it:**
1. Click "New Notice" on the Compliance page.
2. Upload the notice file (any format).
3. Fill in: notice number, authority, date issued, deadline, penalty amount.
4. Save — the notice appears in the dashboard.

### B3. Auto-Classification by Authority — **Available**

For Gmail-imported notices, the system identifies which authority sent it (GST, Income Tax, MCA, RBI, SEBI) using sender domain and email content. The notice is created with the right authority pre-filled. (Higher-accuracy AI classification across 40+ sub-types is a v2.1 upgrade.)

**How to use it:**
1. Connect Gmail (see Section D).
2. Wait for the next scan cycle (every 15 minutes).
3. Detected regulatory emails appear as notices automatically.
4. Review and confirm or correct the auto-assigned authority.

### B4. Risk Scoring with Explainable Factors — **Available**

Every notice receives a risk score from 0 to 100 with a tier label: Critical, High, Medium, or Low. The top 3 factors driving the score are shown in plain English so you understand why.

**How to use it:**
1. Open any notice.
2. View the risk badge at the top of the page.
3. Click the "Why this score?" link.
4. Read the top 3 factors (e.g. "Penalty over Rs. 5L", "Deadline within 7 days", "Senior authority").

### B5. Status Workflow — **Available**

Move notices through five clear stages: Received, Under Review, Response Drafted, Submitted, and finally Resolved or Dismissed. Each transition is logged with who did it and when.

**How to use it:**
1. Open a notice.
2. Click the status dropdown at the top.
3. Pick the next stage.
4. Add an optional note — the activity timeline updates.

### B6. Linked Notices — **Available**

Many regulatory matters span multiple notices: a Show-Cause leads to an Assessment Order, then a Demand. Link them so you see the full chain.

**How to use it:**
1. Open a notice.
2. Click "Link related notice".
3. Search and select the parent or child notice.
4. View the chain in the notice detail page.

### B7. 4-Stage Approval Workflow for Responses — **Available**

Notice responses pass through up to four approval stages: Drafter, Reviewer, Legal, then CFO. Each stage has its own users and permissions. A notice cannot reach Submitted unless every required stage has approved.

**How to use it:**
1. Open a notice and click "Draft Response".
2. Type or paste the response into the editor.
3. Save — the response goes to the Reviewer.
4. Each stage approves or sends it back; once CFO approves, mark as Submitted.

### B8. Auto-Escalation for Critical Notices — **Available**

When a notice scores Critical, the Compliance Head is notified immediately and a record is added to the activity timeline.

**How to use it:**
1. No setup needed — escalation is automatic.
2. Compliance Head sees the alert in the in-app notification bell and email.
3. Open the notice and view the escalation entry in the activity timeline.

### B9. Bulk Status Updates — **Available**

Move many notices through the same stage in one go. Useful for closing a batch of resolved matters.

**How to use it:**
1. Go to the Compliance dashboard.
2. Tick the checkboxes next to multiple notices.
3. Click "Bulk update status".
4. Pick the new status — all selected notices move together; failures (if any) are listed clearly.

### B10. Auditor Read-Only Access (Time-Bound) — **Available**

External auditors get read-only access to notices, audit trails, and reports for a fixed window. After the expiry date their access turns off automatically. A countdown banner shows them how many days remain.

**How to use it:**
1. As Compliance Head, go to the Team page.
2. Invite an auditor by email; set the access end date.
3. They can sign in and view (not edit) until that date.
4. After the date, their access auto-disables.

### B11. Immutable Audit Trail — **Available**

Every action — create, edit, status change, approval, share — is recorded in a tamper-proof log that even administrators cannot alter or delete. Auditors and regulators can review the full history.

**How to use it:**
1. Open any notice.
2. Click the "Audit Trail" tab.
3. See every action, who performed it, and exactly when.
4. Export when an auditor asks (export polish coming in v2.1).

### B12. Permission Matrix for 7 Compliance Roles — **Available**

12 distinct permissions are mapped across 7 roles: Compliance Head, CA Consultant, CFO, Drafter, Reviewer, Legal Team, Finance Team — plus Auditor (time-bound). Each role can do exactly what they should and nothing else.

**How to use it:**
1. As Admin, open the Team page.
2. Assign roles to teammates.
3. Roles enforce themselves automatically across the product.
4. View the role-permission matrix in the Admin settings panel.

### B13. Client Branding — Logo, Website, Address — **Available**

Every onboarded client (your tenant) can register its own company logo, website, and registered office address. The logo and name then appear in the bottom-left of the sidebar so members of that tenant see their own brand alongside TaxSync (co-brand layout — Linear / Stripe pattern).

**Where to find it:**
- Sidebar → Compliance → Clients → pick a client → scroll to the **Branding** section.
- Once saved, the logo + name auto-render in the bottom-left of the sidebar (above the user cluster) for everyone in that tenant.

**How to use it:**
1. Open the client detail page.
2. Scroll to the **Branding** card.
3. Drop or click the logo box — PNG, JPEG, or WEBP, up to 256 KB. SVG is rejected for security (XSS risk).
4. Enter the website (must start with `http://` or `https://`).
5. Enter the registered office address (multi-line).
6. Click **Save**. Logo uploads instantly; website + address save together.
7. Click **Remove logo** under the uploader to clear it.

**Permission:** any team-management role on that client (compliance head, CA consultant). Read-access is open to anyone in the tenant — they see the logo in the sidebar without needing edit rights.

---

## C. Statutory Calendar and Alerts

Never miss a deadline — pre-loaded Indian statutory dates plus reminder alerts.

### C1. 37 Pre-Loaded FY 2025-26 Statutory Deadlines — **Available**

GSTR-1, GSTR-3B, GSTR-9, TDS quarterly returns, Advance Tax instalments, Income Tax Return filings, MCA returns — all pre-loaded for the current financial year.

**How to use it:**
1. Open the Compliance Calendar.
2. View the month — every statutory deadline is visible.
3. Filter to show only the obligations applicable to a specific client.

### C2. Holiday-Aware Deadline Shifting — **Available**

When a deadline falls on a Sunday or a gazetted holiday, the system shifts it to the next working day automatically. Penalty calculations also account for this.

**How to use it:**
1. Add or pick any deadline.
2. The system shows the original and adjusted date.
3. Reminders fire on the adjusted date, not the calendar date.

### C3. Real-Time In-App Notifications — **Available**

A notification bell at the top of the product lights up the moment something requires attention — new notice, status change, deadline approaching, escalation. The bell stays in sync without you having to refresh.

**How to use it:**
1. Look at the bell icon at the top right.
2. A red dot indicates new notifications.
3. Click to view them.
4. Click any notification to jump to the relevant notice or bill.

### C4. Email Alerts — **Available**

Email reminders fire for new notices and approaching deadlines (T-7, T-3, T-1 days) using your registered email address.

**How to use it:**
1. Make sure your profile email is correct.
2. No setup needed — email alerts fire automatically.
3. Check your inbox; act on the alert link.

### C5. Compliance Health Score — **Available**

A single percentage shows how well a client is doing on compliance, calculated over a rolling 90-day window. Higher means fewer overdue notices and faster response times.

**How to use it:**
1. Open the Compliance dashboard.
2. View the health score chip at the top.
3. Click for the breakdown: % responded on time, average response time, overdue count.

### C6. Vendor Invoice Reminders — **Available**

For each compliance client, get reminders 3 days before, 1 day before, and on the overdue day for any tracked vendor invoice (utilities, telecom, subscription services, recurring vendor bills).

**How to use it:**
1. Connect Gmail — invoices are detected automatically.
2. Or add an invoice manually with biller name, amount, and due date.
3. Reminders fire on T-3, T-1, and the overdue day. Capped at 3 reminders per invoice lifetime.

---

## D. Email Integration (Gmail)

Connect Gmail once and the product continuously imports compliance notices and bills.

### D1. One-Click Gmail Connect — **Available**

Sign in with your Google account once. Connection is secure (OAuth 2.0) and you can disconnect any time from the settings page.

**How to use it:**
1. Open the Email page in TaxSync.
2. Click "Connect Gmail".
3. A Google sign-in page opens — pick your account and approve.
4. You return to TaxSync; the connection shows as Active.

### D2. Continuous Background Scanning — **Available**

The product checks your Gmail for new compliance and bill emails every 15 minutes. The cadence is configurable from 5 minutes to 24 hours per credential.

**How to use it:**
1. Once connected, no further action is needed.
2. New notices and bills appear automatically on their dashboards.
3. Adjust the scan frequency from the Email Settings page if needed.

### D3. Filter Rules — **Available**

Decide what happens to incoming emails: route to compliance notices, route to bills, save as a document only, or ignore. Rules match by sender pattern, subject pattern, or Gmail label. Sensible defaults for gov.in and known billers come pre-seeded.

**How to use it:**
1. Open Email Settings.
2. Click "Filter Rules".
3. Add a rule: sender or subject pattern, then choose where to route.
4. Save — the next scan applies the rule.

### D4. Auto-Detect Indian Regulatory Emails — **Available**

Emails from gov.in domains and known regulatory senders (GST, Income Tax, MCA, RBI, SEBI) automatically create a compliance notice with the right authority pre-filled.

**How to use it:**
1. Connect Gmail.
2. Wait for the next scan.
3. Detected regulatory emails appear as notices on the Compliance dashboard.

### D5. Auto-Detect Vendor Invoices — **Available**

Utility, telecom, subscription, and other recurring vendor emails are automatically detected and turned into vendor-invoice records, including biller name, amount, and due date.

**How to use it:**
1. Connect Gmail.
2. Wait for the scan.
3. Invoices appear on the **Vendor invoices** dashboard with due date and amount.

### D6. View Source Email — **Available**

For any notice or bill that came from Gmail, click "View source email" to fetch the original email body on demand. The email is shown in the browser session only — never stored — for privacy.

**How to use it:**
1. Open any Gmail-sourced notice or bill.
2. Click "View source email".
3. The body opens in a panel; refreshing the page discards it.

### D7. Connection Health Monitoring — **Available**

If your Gmail token is revoked or expires, scanning stops and a "Reconnect required" banner appears. After two consecutive scan failures you are alerted via email.

**How to use it:**
1. Sign in to TaxSync.
2. If a banner shows "Reconnect required", click it.
3. Re-authorise Google — scanning resumes automatically.

---

## E. Vendor Invoices and Payments

A dedicated dashboard for tracking the recurring vendor invoices each client owes — detected from Gmail or added manually. (Repositioned from "Bills" in v2.1 — TaxSync is enterprise-only, no consumer/household bill flavour.)

### E1. Vendor Invoice Dashboard with Filters — **Available**

See invoices bucketed into Upcoming, Due Soon, Overdue, and Paid. Per-category aggregates show how much is owed across utilities, telecom, subscriptions, etc.

**How to use it:**
1. Sidebar → Email → **Vendor invoices**.
2. Switch tabs: Upcoming, Due Soon, Overdue, Paid.
3. View totals per category.

### E2. Pre-Deadline Invoice Reminders — **Available**

Reminders fire 3 days before due date, 1 day before, and on the overdue day. Each invoice is capped at three reminders lifetime so the inbox does not fill up.

**How to use it:**
1. No setup needed once an invoice exists.
2. Reminders arrive via email and in-app bell.
3. Click the reminder to open the invoice.

### E3. Mark as Paid — **Available**

Once paid, mark the invoice as Paid with the date, reference number, and method. The transition is logged in the audit trail and stops further reminders.

**How to use it:**
1. Open the invoice.
2. Click **Mark as Paid**.
3. Enter payment date, reference, and method.
4. The invoice moves to the Paid bucket.

### E4. Recurring Invoice Detection — **Available**

When a new invoice arrives from the same biller and account, the system links it to the previous one as a recurring series (monthly, quarterly, or annual).

**How to use it:**
1. Invoices auto-link by biller and last 4 of the account number.
2. Open any invoice to see the full series.
3. Spot a missing month? An anomaly alert appears in the bell.

### E5. Missing-Month Anomaly Detection — **Available**

If a recurring invoice has arrived every month for the last six months and suddenly skips a cycle, the system surfaces it as an anomaly so the team can check whether the invoice is actually due.

**How to use it:**
1. Look for the "Missing invoice?" alert in the notification bell.
2. Open the recurring series to confirm.
3. Add the invoice manually if a paper copy exists.

### E6. Multi-Channel Reminder Delivery — **Available**

Reminders are delivered via email and the in-app notification bell. SMS delivery is scaffolded and ships once telecom registration completes.

**How to use it:**
1. Use whichever channel is preferred for monitoring.
2. Both update in sync — actioning one clears the other.

---

## F. AI Document Intelligence

The intelligence layer underpinning classification, extraction, summaries, and risk.

### F1. Auto-Classification Across 7 Document Categories — **Available**

Approximately 85% accurate auto-categorisation of any uploaded document into one of seven common categories. Manual override available.

**How to use it:** see Section A3.

### F2. 6 AI Providers with Automatic Fallback — **Available**

The product talks to multiple AI providers under the hood. If one is slow or unavailable, the next is used automatically. You never see an error from a provider outage.

**How to use it:**
1. No user action needed — fallback is silent and automatic.
2. Extraction and summaries simply keep working.

### F3. Smart Extraction (Dates, Amounts, Vendors) — **Available**

Pulls structured fields from invoices, receipts, and tax notices.

**How to use it:** see Section A4.

### F4. AI-Generated Summaries — **Available**

Plain-English one-paragraph summaries for any document.

**How to use it:** see Section A5.

### F5. Risk Scoring for Compliance Notices — **Available**

0-100 risk score with tier label and three explainable factors per notice.

**How to use it:** see Section B4.

### F6. Human Review Queue for Low-Confidence Classifications — **Available**

When the AI is not confident enough, the notice is routed to a human review queue instead of auto-assigning a category. (Active learning improvement comes in v2.1.)

**How to use it:**
1. As Compliance Head, open the "Review Queue" page.
2. Review pending items.
3. Confirm or correct each — the system learns from your decision.

---

## G. Search and Reporting

Find anything fast, run reports, export to spreadsheets.

### G1. Full-Text Search Across All Documents — **Available**

Search anywhere in document content, not just file names.

**How to use it:** see Section A9.

### G2. Cross-Entity Unified Search — **Available**

A single search box searches both documents and compliance notices. Results show the type (Document or Notice) so you know where to click.

**How to use it:**
1. Type into the global search.
2. Results appear with type badges.
3. Click anything — it opens in its native page.

### G3. Fuzzy Matching — **Available**

Typos and partial words still find their target.

**How to use it:** type whatever you remember; the system handles small mistakes.

### G4. Filter by Authority, Status, Risk, Date — **Available**

Compliance lists can be filtered on any combination of authority, status, risk tier, deadline window, and amount.

**How to use it:**
1. Open the Compliance dashboard.
2. Use the filter chips at the top.
3. Combine filters as needed.
4. Save the URL to share or revisit later.

### G5. Pre-Built Reports — **Available**

Penalty by Authority, Notice Volume by Status, Response Time Percentiles, Compliance Health Summary — all available out of the box.

**How to use it:**
1. Click "Reports" in the Compliance sidebar.
2. Pick a report.
3. Adjust date range and client filter.
4. View charts and tables.

### G6. CSV Export — **Available**

Every report and list exports to CSV for use in Excel or Google Sheets.

**How to use it:**
1. Open any report or list.
2. Click "Export CSV".
3. The file downloads to your computer.

---

## H. Multi-User Access and Security

Access controls for teams, encryption for sensitive data.

### H1. Email and Password Sign-In — **Available**

Standard email and password registration with industry-grade password storage.

**How to use it:**
1. Click "Sign Up".
2. Enter email and password.
3. Verify email if prompted.
4. Sign in.

### H2. Sign In with Google or Microsoft — **Available**

One-click sign-in with a Google or Microsoft account. No separate password to remember.

**How to use it:**
1. Click "Sign in with Google" or "Sign in with Microsoft".
2. Approve the access prompt.
3. You are signed in.

### H3. 7 Compliance Roles plus Auditor — **Available**

Compliance Head, CA Consultant, CFO, Drafter, Reviewer, Legal Team, Finance Team — plus Auditor for time-bound external access.

**How to use it:** see Section B12.

### H4. Cross-Client View for Senior Roles — **Available**

Compliance Head, CA Consultant, and CFO can view all clients in one combined dashboard. Other roles see only the active client.

**How to use it:**
1. As a senior role, open the client switcher.
2. Pick "All Clients".
3. Dashboards now aggregate across all your clients.

### H5. Admin User Management — **Available**

Admins invite teammates, assign roles, and revoke access from a dedicated Team page.

**How to use it:**
1. Open the Team page.
2. Click "Invite Member".
3. Enter email and role.
4. They receive an invite link by email.

### H6. Auto-Logout and Session Management — **Available**

Sessions refresh automatically on activity and end after a period of inactivity for security.

**How to use it:**
1. No setup needed.
2. Inactive sessions sign out automatically.
3. Sign back in to resume.

### H7. Encrypted Sensitive Fields — **Available**

GSTIN, PAN, penalty amounts, and similar fields are encrypted in storage so they cannot be read even if the database is breached.

**How to use it:**
1. No user action — encryption is always on for sensitive fields.

### H8. Production Security Hardening — **Available**

The platform applies industry standards: rate limiting on login attempts, secure HTTP headers, and CSRF protection on every action.

**How to use it:**
1. No user action — these defences are always on.

---

## I. Analytics and Reporting

Dashboards for documents, compliance, and bills.

### I1. Documents Dashboard — **Available**

Total document count, monthly uploads trend, category breakdown.

**How to use it:** see Section A10.

### I2. Compliance Dashboard with Risk Distribution — **Available**

A pie chart of notices by risk tier (Critical / High / Medium / Low), monthly volume, and a status snapshot.

**How to use it:**
1. Open the Compliance Dashboard.
2. View the risk distribution pie.
3. Click any slice to filter the notice list.

### I3. Compliance Health Score (Rolling 90 Days) — **Available**

A single percentage at the top of every client view.

**How to use it:** see Section C5.

### I4. Per-Authority Penalty Totals — **Available**

How much have you been hit with from GST vs Income Tax vs MCA?

**How to use it:**
1. Open Reports > Penalty by Authority.
2. Pick the date range.
3. View the bar chart with per-authority totals.

### I5. Notice Response Time Analytics — **Available**

Median, 75th percentile, and 90th percentile response times across all notices.

**How to use it:**
1. Open Reports > Response Time.
2. Pick date range and client.
3. View the percentile chart.

### I6. CSV Export of Every Report — **Available**

See Section G6.

---

## J. BYOK AI Assistant — Bring Your Own Key

A built-in AI assistant powered by **your own** Anthropic Claude or Google Gemini API key. Costs go to your provider account; TaxSync never charges for AI. The assistant is hard-prompted to only answer questions about TaxSync work — anything off-topic is refused. Available since 2026-05-08.

### J1. Connect Your AI Provider — **Available**

Pick a provider (Claude or Gemini), pick a model, paste your API key, save. The key is encrypted at rest using the same Fernet cipher that protects Gmail refresh tokens (INFRA-06). The plaintext is never returned to the browser after save.

**Where to find it:**
- Sidebar → Settings → **AI assistant**
- OR: Dashboard → Quick actions → **Ask AI** tile (4th tile, violet)

**How to use it:**
1. Open Settings → AI assistant.
2. Pick provider — Anthropic Claude or Google Gemini.
3. The default model auto-fills (`claude-sonnet-4-6` or `gemini-1.5-flash`). Override only if your account has access to a different model.
4. Paste your API key.
5. Click **Test** — sends a one-token ping; success shows latency.
6. Click **Save** — the key is encrypted and stored.
7. Replacing the key is the same flow; **Disconnect** wipes it.

**Permission:** restricted to admin-grade roles (compliance head, CA consultant). Read access (knowing which AI is connected) is open to anyone in the tenant.

### J2. AI Notice Summary + Recommended Actions — **Available**

On any compliance notice, two on-demand AI buttons:
- **Summarize** — a 4-6 line digest covering authority, core demand, tax/penalty/interest amounts, deadline, and a one-word risk tier.
- **Suggest actions** — a list of 3-5 concrete next steps for the compliance team, each with a one-line rationale and an urgency tier (high/medium/low) shown as a coloured stripe.

**Where to find it:**
- Compliance → Notices → open any notice → **AI assistant** panel at the top of the right column.

**How to use it:**
1. Open any notice (`/dashboard/compliance/notices/<id>`).
2. Find the **AI assistant** card in the right column.
3. Click **Summarize** — wait 2-5 seconds; markdown summary + key-points list + deadline render below.
4. Click **Suggest actions** — action cards appear, urgency-coloured.

If no AI key is connected, the panel shows **"Connect AI"** as a one-click link to Settings.

### J3. AI Vendor Invoice Summary + Actions + Payment Timing — **Available**

On any vendor invoice, three on-demand AI buttons:
- **Summarize** — a 2-3 line digest plus an automatic **anomalies** list (amount unusually high vs same-vendor history, missing reference, due-date in the past, recurrence drift).
- **Suggest actions** — 2-4 next steps (mark paid, flag duplicate, request invoice copy, schedule reminder, etc.) with rationale and urgency.
- **Payment timing** — a recommendation (pay now / wait until T-1 / pre-pay for early-payment discount) with rationale and an optional suggested payment date, rendered in an accent-tinted box.

**Where to find it:**
- Sidebar → Email → Vendor invoices → open any invoice → **AI assistant** panel between payment-details and the action row.

**How to use it:**
1. Open any vendor invoice (`/dashboard/email/bills/<id>`).
2. Find the **AI assistant** card.
3. Click any of the three buttons.

### J4. Scope Lock — Strictly TaxSync Work Only — **Available**

The system prompt hard-restricts the AI to:
1. Indian tax / regulatory notices (GST, Income Tax, MCA, RBI, SEBI)
2. Compliance deadlines and response drafts
3. Vendor invoices for the tenant's clients
4. The drafter → reviewer → legal → CFO chain
5. TaxSync workflow guidance

Anything else — code, weather, general knowledge, jailbreak prompts, mixed in-scope+out-scope questions — gets refused with a single line. The frontend translates this into a soft toast: **"I can only help with TaxSync compliance and finance work."**

This is defence-in-depth, not a cryptographic boundary — a determined user with their own key could still craft prompts to break out. But the prompt prevents accidental general-purpose usage and limits cost burn from off-topic queries.

**Permission:** any active member of the tenant can run AI tasks (gated by `notice:view`). Only admins can manage the credential.

### J5. Provider Cost Transparency — **Available**

Costs are charged directly to the user's Anthropic or Google account. TaxSync never bills for AI usage. The Settings page shows the connected provider, model, and "last used" timestamp so admins can spot stale credentials.

**How to use it:**
1. Open Settings → AI assistant.
2. The connected card shows: provider, model, last-used timestamp.
3. Check your provider's billing dashboard for actual spend.

---

## Pending Features (Next Releases)

These features are committed but not yet shipped. Estimated release windows below.

| Feature | Status | Target Release |
|---------|--------|----------------|
| Direct integration with GST, Income Tax, MCA portals (auto-fetch notices) | Blocked | Pending regulatory access decisions |
| Higher-accuracy AI classification across 40+ notice sub-types | Planned | v2.1 (2026 Q3) |
| AI-drafted response generation from notice templates | Planned | v2.1 (2026 Q3) |
| 20+ pre-built response templates with variable substitution | Planned | v2.1 (2026 Q3) |
| Evidence package PDF merge with auto table-of-contents | Planned | v2.1 (2026 Q3) |
| GSTR-2A/2B vs GSTR-3B reconciliation report | Planned | v2.1 (2026 Q3) |
| Searchable regulation library (GST Act, IT Act, Companies Act, FEMA, SEBI) | Planned | v2.1 (2026 Q3) |
| Larger-scale search (Elasticsearch) for very high notice volumes | Planned | v2.1 (2026 Q3) |
| SMS alerts | Planned | v2.1 — pending DLT registration |
| Per-user alert preferences (T-7 / T-3 / T-1 customisation) | Planned | v2.1 (2026 Q3) |
| Calendar export to Google Calendar / Outlook (.ics) | Planned | v2.1 (2026 Q3) |
| Severity-weighted compliance score | Planned | v2.1 (2026 Q3) |
| Outlook, Yahoo, and other (IMAP) email integrations | Planned | v2.1 (2026 Q3) |
| Public AI chat ("Ask AI about my notices") | Planned | v3.0 (2027) |
| Outbound email replies via AI drafting | Planned | v3.0 (2027) |
| Native mobile apps (iOS / Android) | Out of Scope | Web-first sufficient |
| WhatsApp Business notifications | Out of Scope | Email + SMS sufficient |
| Multi-language (Hindi, regional) interface | Out of Scope | English standard for compliance |

---

## Feature Scorecard

A quick numerical view.

| Bucket | Count |
|--------|-------|
| Available now | 70 features |
| In Progress | 0 features |
| Planned (v2.1) | 13 features |
| Planned (v3.0) | 2 features |
| Blocked (external dependency) | 1 feature group (government portal direct integration) |
| Out of Scope | 3 features (mobile, WhatsApp, multi-language) |

**Available-feature breakdown by area:**

| Area | Available |
|------|-----------|
| Document Management | 10 |
| Compliance Notice Management | 13 (added B13 Client Branding 2026-05-08) |
| Statutory Calendar and Alerts | 6 |
| Email Integration (Gmail) | 7 |
| Vendor Invoices and Payments | 6 (repositioned from "Bills and Payments" 2026-05-08) |
| AI Document Intelligence | 6 |
| Search and Reporting | 6 |
| Multi-User Access and Security | 8 |
| Analytics and Reporting | 6 (overlaps included for completeness) |
| BYOK AI Assistant | 5 (new section J, added 2026-05-08) |

---

## Glossary

Plain definitions of unavoidable terms.

- **GSTIN** — A unique 15-character ID issued to a business under Goods and Services Tax. Like a tax-ID for a specific GST registration.
- **PAN** — Permanent Account Number. A 10-character ID from Income Tax that identifies a person or entity.
- **CIN** — Corporate Identification Number, a 21-character code for a company registered with the MCA.
- **GST** — Goods and Services Tax. The federal indirect tax in India.
- **TDS** — Tax Deducted at Source. Tax withheld at the time of payment (salary, contractor fees, rent over a threshold, etc.).
- **ITR** — Income Tax Return. Annual filing with the Income Tax department.
- **MCA** — Ministry of Corporate Affairs. Regulator for companies (filings like ROC).
- **RBI** — Reserve Bank of India. Banking and forex regulator.
- **SEBI** — Securities and Exchange Board of India. Capital markets regulator.
- **GSP** — GST Suvidha Provider. An authorised intermediary that connects software to the GST portal.
- **DLT Registration** — A telecom-regulator process required before a brand can send SMS in India.
- **Notice** — A formal communication from a regulator demanding information, payment, or response by a deadline.
- **Show-Cause Notice** — A notice asking the recipient to explain why a proposed action (penalty, demand) should not be taken.
- **Compliance Head** — The senior in-house owner of regulatory matters. Typically approves the most serious responses.
- **CA Consultant** — A Chartered Accountant external to the client, often managing many clients across many GSTINs.
- **CFO** — Chief Financial Officer. Final approver on responses with material financial impact.
- **Drafter** — The team member who writes the first version of a response.
- **Reviewer** — The peer who reviews a draft before it goes to Legal.
- **Legal Team** — The team responsible for legal accuracy and regulation citations in a response.
- **Finance Team** — Reviewers of tax-specific notices and reconciliation data.
- **Auditor** — An external party with time-bound, read-only access for inspection or assurance work.
- **Audit Trail** — A tamper-proof, timestamped record of who did what, when.
- **Risk Tier** — A label (Critical, High, Medium, Low) summarising how urgent a notice is.
- **OAuth** — A standard authorisation flow used to connect your Google or Microsoft account safely without sharing your password.
- **OCR** — Optical Character Recognition. Reading text from images and scanned documents.

---

## Contact and Support

For questions, training, or onboarding support, contact:

- **Project Lead:** Sravan (TaxSync, Product Labs, IIIT Hyderabad)
- **Email:** munnasrav45@gmail.com
- **Documentation:** README.md and user-facing help in the app
- **Status updates:** STATUS_REPORT.md

---

*TaxSync — Smart Document Management and Compliance System*
*Document version: v2.1 — released 8 May 2026 (adds B13 Client Branding, Section J BYOK AI, Vendor Invoice rebrand)*
