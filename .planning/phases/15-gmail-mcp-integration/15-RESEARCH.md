# Phase 15: Gmail MCP Integration & Email Document Ingestion - Research

**Researched:** 2026-05-07
**Domain:** Gmail OAuth2 ingestion + MCP server (FastMCP) + APScheduler polling + bill detection + rule-based compliance routing
**Confidence:** HIGH (FastMCP + Gmail API + Google OAuth — all verified via Context7/official docs); MEDIUM (subprocess-vs-in-memory MCP transport choice — D-31 needs revisit); MEDIUM (Indian regulatory sender domains — list curated from official sources but should be operator-tunable post-deploy)

## Summary

Phase 15 implements a one-time Gmail OAuth2 connection that produces a refresh token, plus an APScheduler-driven polling loop that fetches matching emails on a per-credential cadence and routes them three ways: (a) compliance notices (sender-domain regex + subject keyword detector → auto-create `ComplianceNotice` with `status=Received`), (b) bills (sender heuristics + LLM extraction → new `bills` table linked optionally to `documents` via `source_document_id`), (c) DMS-only documents. Six FastMCP tools expose Gmail capabilities to internal Phase 12 agents.

Three findings reshape the plan:

1. **D-31's `subprocess.Popen` design conflicts with FastMCP's transport model.** FastMCP stdio assumes the *client* spawns the *server* (Claude Desktop pattern). For an internal-only consumer (Phase 12 agents in the same Python process), FastMCP's **in-memory transport** — `Client(server_instance)` — eliminates subprocess entirely with cleaner lifecycle, no IPC overhead, and direct exception propagation. Recommend planner re-evaluate: stdio-subprocess only adds value if Phase 12 agents run as separate OS processes (which they don't in v2.0).
2. **D-17's "reuse Phase 10 spaCy NER" is broken** — `app/ml/compliance/ner.py:49` raises `NotImplementedError` because the custom NER pipeline was deferred to v2.1 along with BERT. Phase 15 must either extend the existing **regex_patterns.py** (GSTIN/PAN/CIN/section refs already implemented) for body-text extraction, or skip NER and use only regex+LLM fields. Recommend regex-only for v2.0 and document the v2.1 NER swap path identically to D-16's BERT swap pattern.
3. **Phase 14 PortalFetchLog does not exist yet** (Phase 14 is BLOCKED). The `gmail_fetch_log` table must land standalone in Phase 15; the schema is then a template the future Phase 14a copies. Migration ordering is straightforward — no Phase 14 dependencies in the chain.

**Primary recommendation:** Use FastMCP 3.2.4 with **in-memory transport** (no subprocess), `google-api-python-client` 2.196.0 for Gmail API, refresh tokens encrypted via the existing `app.compliance.utils.pii_encryption` Fernet helper, and an APScheduler `IntervalTrigger` job per credential persisted in the existing `apscheduler_jobs` table introduced by Phase 11.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### MCP Server Architecture

- **D-01:** Run the Gmail MCP server as a sidecar process inside the existing backend container (not a separate microservice).
- **D-02:** Expose 6 MCP tools in v2.0: `gmail_search`, `gmail_read_message`, `gmail_list_attachments`, `gmail_get_attachment`, `gmail_list_labels`, `gmail_modify_labels` (read-only label modification limited to system-managed labels like `dms-ingested`).
- **D-03:** No outbound tools (`gmail_send`, `gmail_create_draft`, `gmail_reply`) in v2.0 — read-only scope eliminates a class of misuse and keeps OAuth scope minimal (`gmail.readonly` + `gmail.modify` for label-only writes).
- **D-04:** All MCP tool invocations write a row to `audit_log` with actor=user, action=`MCP_TOOL_CALL`, target=tool name, before/after capturing args (PII-redacted via Phase 9 INFRA-06 pattern). Phase 9 immutability triggers apply automatically.
- **D-05:** MCP server is gated by the same `require_compliance_permission` dependency factory introduced in Plan 09-04 — only users with the `email_integration:use` permission can connect or invoke tools.
- **D-29:** **MCP library = FastMCP**. Decorator-based tool registration over the official `mcp` Python SDK; spec-compliant; ~5x less boilerplate per tool than raw SDK.
- **D-30:** **Transport in v2.0 = stdio only**. All in-scope MCP consumers are internal Phase 12 agents. HTTP/SSE deferred to v2.1.
- **D-31:** **MCP server lifecycle = backend entrypoint spawns child via `subprocess.Popen`**. FastAPI app's startup hook launches the MCP sidecar; dies when backend dies; shares env (DATABASE_URL, encryption keys, ALEMBIC head).

#### OAuth & Token Storage

- **D-06:** OAuth client registered as a "Web application" in Google Cloud Console with offline access. Authorized redirect URI is `${BASE_URL}/api/email/gmail/oauth/callback`. Scopes: `https://www.googleapis.com/auth/gmail.readonly`, `https://www.googleapis.com/auth/gmail.modify`.
- **D-07:** Refresh tokens stored in a new `gmail_credentials` table, AES-Fernet encrypted at the field level. Access tokens are never persisted — derived on demand and Redis-cached with TTL = `expires_in` minus 60s skew.
- **D-08:** Token revocation handler — when Gmail returns `invalid_grant`, mark the credential row `status=REVOKED`, disable the scanner job, emit a `gmail.connection.lost` event.
- **D-09:** Per-client OAuth — each `gmail_credentials` row is scoped to `(user_id, client_id)`. Cross-client read forbidden by RLS.

#### Ingestion Pipeline

- **D-10:** Scanner runs on APScheduler. Default cadence: every 15 minutes per active credential. User-configurable per credential (5min - 24hr).
- **D-11:** Filter rules stored in `gmail_filter_rules` table — `(credential_id, sender_pattern, subject_pattern, label_include, label_exclude, route_to)`.
- **D-12:** Default filter rules seeded on connect: gov.in domain → compliance_notice; common biller domains → bill.
- **D-13:** Deduplication — composite UNIQUE on `(credential_id, gmail_message_id)` for messages, plus per-attachment SHA-256 hash UNIQUE within a credential.
- **D-14:** Attachment ingestion reuses the v1.0 document upload path. The Document.source_email_id FK records provenance.
- **D-15:** GmailFetchLog mirrors Phase 14 PortalFetchLog three states: `SUCCESS_EMPTY` / `SUCCESS_WITH_RESULTS` / `FETCH_FAILED`.

#### Compliance Auto-Routing

- **D-16 (REVISED):** **v2.0 path uses a rule-based detector, NOT BERT.** Sender-domain regex + subject keyword match. Binary confidence (matched → auto-create at status=Received; unmatched → Phase 10 review queue).
- **D-17:** Notice metadata extraction reuses Phase 10 spaCy NER. *(Research finding: NER is `NotImplementedError`; see Phase Constraints below.)*
- **D-18:** A "View original email" deep-link on the notice detail page opens a backend endpoint that fetches the email via MCP `gmail_read_message`.
- **D-32:** **Auto-created notice status = Received + 'Auto-imported from Gmail' badge**. Indistinguishable from manual upload at the API/audit/transition level.
- **D-33:** **Forwarded-notice handling = route to `dms_only`** when content matches but sender-regex fails. Compliance head manually links via Plan 09-07 link-notice UI.

#### Email Body PII Lifecycle

- **D-34:** **Fetch-once / classify+extract / discard.** Body lives only in Python locals for ~seconds.
- **D-35:** **Audit log = one row per `MCP_TOOL_CALL` with body SHA-256.** Schema: `actor_id`, `action='MCP_TOOL_CALL'`, `target=tool_name`, `args={message_id, body_sha256, attachment_ids[], attachment_sha256s[]}`.
- **D-36:** **Audit-arg redaction = bodies + attachments + subjects + senders all PII-redacted; keep IDs + SHA-256.** Even sender domain only — not full address.

#### Bill Management

- **D-19 (REFINED):** **Hybrid Bill data model.** New `bills` table holds payment-cycle metadata. Optional `source_document_id` FK → `documents.id` when a PDF is attached. Bills WITHOUT attachments have `source_document_id=NULL`.
- **D-20:** Bill fields: `biller_name`, `biller_category` (utility/telecom/credit_card/subscription/other), `amount_due` (Decimal INR), `currency` default INR, `due_date`, `account_number_last4`, `payment_status`, `is_recurring`, `recurrence_period`, `parent_bill_id`, `source_document_id`, `source_email_id`.
- **D-21:** Extraction reuses v1.0 LLM service with a new bill-specific prompt template. Falls back to local regex.
- **D-22:** Reminders piggyback on Phase 11 alert infrastructure with a `BILL_DUE_SOON` event type (T-3, T-1, overdue tiers). Cool-down per bill: max 3 reminders per lifetime.
- **D-23:** Recurring bill detection — when a new bill matches an existing bill's `(biller_name, account_number_last4)`, link via `parent_bill_id`. Biller name normalized via regex.
- **D-37:** **Bill detail page = `/dashboard/email/bills/[id]`**.

#### Frontend

- **D-24:** New `/dashboard/email` route tree. Top-level pages: `/email/connect`, `/email/settings`, `/email/activity`, `/email/bills`.
- **D-25:** Compliance dashboard gains a `source` filter chip (manual/portal/gmail). Same chip applied to `/dashboard/documents/*` listings.
- **D-26:** Bill dashboard pattern matches v1.0 admin dashboard.

#### AI Agent Surface (Internal Only)

- **D-27 (SUPERSEDED by D-30):** stdio-only choice means there is no listener at all. Internal-only is enforced by the absence of a network surface.
- **D-28 (REFINED):** Agent identity = the user who connected the credential. Each tool call's caller passes the originating user's `client_id` + `user_id` as call args (validated server-side). RLS context set via `set_config('app.current_client_id', ...)`.

### Claude's Discretion

- Scanner cadence default tuning (seed D-10 says 15min; may adjust based on Gmail quota analysis; exposed user-configurable 5min-24hr regardless)
- Pydantic schemas for MCP tool args
- MCP error envelope format (FastMCP defaults — return type-annotated exceptions)
- Bill `payment_method` enum starting set: `upi | netbanking | card | cash | cheque | autopay | other`
- Bill detail page layout details
- Gmail label management UX in v2.0 (auto-apply `dms-ingested` silently)
- LLM prompt versioning for bill extraction (`bills.extraction_prompt_rev` field)
- Migration ordering relative to Phase 14 (Phase 14a may ship first; Phase 15 migrations must be additive only)

### Deferred Ideas (OUT OF SCOPE)

- Multi-provider email MCP (Outlook/Yahoo/IMAP) — Phase 14 PORT-05 retains the generic IMAP path.
- User-facing AI chat surface ("Ask AI about my Gmail") — internal agents only.
- Outbound email tools (`gmail_send`, `gmail_reply`, `gmail_create_draft`) — adds OAuth scope blast radius.
- Business AP invoice ingestion — overlaps with v1.0 `invoices` category and a future AP/AR workflow.
- Multi-account support per user — single Gmail per user-client pair in v2.0.
- Gmail label management UI — minimum-viable label filtering only.
- Calendar integration — covered by ALERT-10 in Phase 11.
- MCP HTTP/SSE transport — D-30 ships stdio only.
- BERT-based compliance classifier — v2.1.
- Forwarded-notice content classification — v2.1 BERT.
- Auto-Received pre-acknowledgement status — rejected (D-32).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **EMAIL-01** | User can connect Gmail via OAuth 2.0 with offline access (refresh-token), per (user, client) pair | OAuth 2.0 web-server flow with `access_type=offline` + `prompt=consent`. Backend redirect handler at `/api/email/gmail/oauth/callback`. CSRF protection via signed-JWT state (existing pattern in `auth.py:309-315`). |
| **EMAIL-02** | Six MCP tools exposed | FastMCP 3.2.4 with `@mcp.tool` decorators. Tool args derived from Pydantic models. Recommended: in-memory transport (revisit D-31 subprocess). |
| **EMAIL-03** | Refresh-token Fernet-encrypted; access tokens Redis-cached only | Existing `app.compliance.utils.pii_encryption.encrypt_field()` returns BYTEA-suitable bytes. Redis access-token cache key = `gmail:access:{credential_id}`, TTL = `expires_in - 60`. |
| **EMAIL-04** | Filter rules per credential (sender, subject, labels, route_to) | Standard SQLAlchemy ORM table with composite index on `(credential_id, route_to)`. Seed defaults via Alembic data migration. |
| **EMAIL-05** | Attachment ingestion reuses v1.0 upload pipeline; `source_email_id` FK | `Document.source_email_id` is a NEW column; need Alembic migration extending `documents`. Existing `storage_service.save_file()` and Celery `process_document_task` reused unchanged. |
| **EMAIL-06** | Auto-create ComplianceNotice on rule match; route low-confidence to Phase 10 review queue | Phase 10 `enqueue_low_confidence()` exists at `review_queue_service.py`. Rule-detector returns binary confidence (1.0 matched / 0.5 uncertain). |
| **EMAIL-07** | GmailFetchLog three-state monitoring | Phase 14 PortalFetchLog does NOT exist yet — Phase 15 lands the schema standalone (template for future Phase 14). |
| **EMAIL-08** | Dedup via UNIQUE on `(credential_id, gmail_message_id)` and per-attachment SHA-256 | Standard PostgreSQL UNIQUE indexes. Per-attachment hash computed during ingestion. |
| **EMAIL-09** | Audit log per MCP tool call (PII-redacted) | Existing `log_audit_event()` from `app/services/audit_service.py:85`. Hardened path = `log_audit_event_strict` for regulatory-critical entries. PII redaction via existing pattern. |
| **EMAIL-10** | Connection health monitoring; `invalid_grant` triggers REVOKED + alert | `google.auth.exceptions.RefreshError` is the Python exception. Two consecutive FAILED entries fire a `gmail.connection.lost` Phase 11 alert. |
| **BILL-01** | Auto-detect bill emails (utility/telecom/credit_card/subscription) via sender heuristics + LLM | Sender domain regex against seeded biller list + LLM classification fallback when sender unknown. |
| **BILL-02** | Bill metadata extraction — biller, amount, due_date, account_number_last4 | Reuse `extract_with_llm(text, "bills")` — `CATEGORY_FIELDS["bills"]` already includes `["bill_number", "billing_date", "due_date", "total_amount", "vendor", "account_number"]`. Add bill-specific prompt template overriding defaults. Regex fallback for amount + date. |
| **BILL-03** | Bill dashboard with Upcoming/Due Soon/Overdue/Paid filters | Pattern matches v1.0 admin dashboard cards + filter table; Zustand store; React Query fetching. |
| **BILL-04** | Pre-deadline reminders (T-3, T-1, overdue) via Phase 11 alert pipeline | NEW alert types `bill_t3`, `bill_t1`, `bill_overdue` added to `VALID_ALERT_TYPES` in `app/compliance/models/alert.py:37`. APScheduler job per bill mirrors `schedule_deadline_alerts()` pattern. |
| **BILL-05** | Mark-as-paid workflow with payment_date/reference/method; audit log entry | Service-layer-only mutation (mirror Phase 9 D-D pattern). State machine: `pending → paid` (overdue → paid also valid). |
| **BILL-06** | Recurring bill detection via `parent_bill_id` link on `(biller_name, account_number_last4)` match | Partial unique index on normalized `(biller_name, account_number_last4)` per credential where account_number_last4 is not null. Missing-month anomaly via Phase 11 anomaly detection. |
</phase_requirements>

## Project Constraints (from /home/sraav/.claude/CLAUDE.md)

The project does not have a per-repo CLAUDE.md. The relevant global rules:

- **No emojis** in code, comments, or commit messages.
- **No backwards-compat shims** for unused code; delete it.
- **Minimal comments** — only the WHY when non-obvious.
- **Validate at system boundaries only** — trust internal code.
- **Conventional commits**: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`, `perf:`.
- **No Claude/Anthropic co-author trailers** in commits or PRs.
- **For bugs, find root cause** before patching the symptom.
- **Don't suppress errors** with try/catch just to make tests pass.
- **Reversible local actions** (edit a file, run tests): act, no need to ask.
- **Hard-to-reverse actions** (force push, drop table, delete branch, rm -rf, npm uninstall): always ask first.

## Standard Stack

### Core (verified versions, May 2026)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **fastmcp** | 3.2.4 (PyPI, 2026-04) | MCP server with decorator-based tool registration | Built ON the official `mcp` SDK; ~5x less boilerplate; ~70% of MCP servers across all languages use FastMCP. |
| **mcp** | 1.27.0 (transitive via fastmcp) | Underlying MCP protocol Python SDK | Spec-compliant — FastMCP delegates protocol handling to it. |
| **google-api-python-client** | 2.196.0 | Official Gmail API Python client | The supported, generated client; handles auth + retry on 429 by default; pagination helpers. |
| **google-auth** | (transitive ≥2.30) | OAuth credentials lifecycle | Provides `Credentials` class + automatic refresh; raises `google.auth.exceptions.RefreshError` on `invalid_grant`. |
| **google-auth-oauthlib** | 1.4.0 | Web-server OAuth flow helper | `Flow.from_client_config()` is the canonical web-app flow entrypoint. |
| **APScheduler** | 3.11.0 (already in `requirements.txt`) | Per-credential polling jobs | Phase 11 already configured `SQLAlchemyJobStore` against `apscheduler_jobs` table; Phase 15 reuses. |
| **cryptography** | (transitive via Phase 9 — already pinned) | Fernet symmetric encryption for refresh tokens | Re-uses INFRA-06 helper at `app.compliance.utils.pii_encryption`. |
| **redis** | 5.0.1 (already in `requirements.txt`) | Access-token cache with TTL | Existing connection in `app/main.py:189` health check. |
| **httpx** | 0.25.2 (already in `requirements.txt`) | Direct HTTP for OAuth token exchange (existing `oauth_service.py` pattern) | Already used in `GoogleOAuth.exchange_code` — extend the same pattern. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pydantic** | 2.11.3 (existing) | Tool argument schemas for FastMCP | When auto-derivation from type hints isn't strict enough (e.g., bounded `max_results: int = Field(default=50, ge=1, le=500)`). |
| **dateparser** | 1.2.0 (existing) | Parse Indian-format dates from bill bodies | Already used by Phase 10 NER plan; reuse for bill due-date extraction. |
| **structlog** | 25.5.0 (existing) | Structured logging for scanner runs | Match existing `app.tasks.document_tasks` pattern. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastMCP (D-29 locked) | Raw `mcp` SDK | ~5x more boilerplate per tool; manually manage protocol envelope; 6 tools = 6 reasons FastMCP wins. |
| FastMCP **stdio + subprocess.Popen** (D-31) | FastMCP **in-memory transport** | **Strongly recommend revisiting D-31.** In-memory `Client(server_instance)` makes zero subprocess, zero IPC, direct Python exception propagation, simpler lifecycle. Only reason to keep stdio-subprocess is if Phase 12 agents become out-of-process in v2.1 (which is not the v2.0 plan). See Pitfall 1 below. |
| google-api-python-client | Direct httpx calls to `gmail.googleapis.com` | The official client handles 429 retries, pagination helpers, batch requests, OAuth credential refresh. Building these from raw httpx duplicates well-tested code. |
| OAuth via custom flow | Reuse the existing `GoogleOAuth` pattern in `app/services/oauth_service.py` | The existing pattern targets login-only OAuth (`openid email profile` scopes). Phase 15 needs a separate Gmail-scoped flow with `gmail.readonly` + `gmail.modify` and offline access. **Add a new `GmailOAuth` class alongside** — do NOT reuse the login `GoogleOAuth` class because the scopes diverge. |

**Installation (additive to existing `requirements.txt`):**
```bash
pip install fastmcp==3.2.4 google-api-python-client==2.196.0 google-auth-oauthlib==1.4.0
# google-auth pulled transitively ≥2.30
```

**Version verification (run in plan validation):**
```bash
pip index versions fastmcp | head -1     # confirm 3.2.4 still latest
pip index versions google-api-python-client | head -1
pip index versions mcp | head -1          # confirm fastmcp 3.2.4 compatible
```
Versions confirmed against PyPI registry on 2026-05-07 — fastmcp 3.2.4, mcp 1.27.0, google-api-python-client 2.196.0, google-auth-oauthlib 1.4.0.

## Architecture Patterns

### Recommended Project Structure

```
backend/app/
├── email/                                # NEW Phase 15 package (NOT under compliance/ — bills are not compliance)
│   ├── __init__.py
│   ├── models/
│   │   ├── credential.py                 # GmailCredential ORM
│   │   ├── filter_rule.py                # GmailFilterRule ORM
│   │   ├── fetch_log.py                  # GmailFetchLog ORM (template for future Phase 14a)
│   │   ├── message_log.py                # GmailMessageLog ORM (dedup + audit anchor)
│   │   └── bill.py                       # Bill ORM (hybrid model per D-19)
│   ├── schemas/                          # Pydantic request/response schemas
│   │   ├── credential.py
│   │   ├── filter_rule.py
│   │   └── bill.py
│   ├── routers/                          # FastAPI routers (mounted at /api/email)
│   │   ├── oauth.py                      # /api/email/gmail/oauth/{authorize,callback}
│   │   ├── credentials.py                # CRUD + status
│   │   ├── filter_rules.py               # CRUD
│   │   ├── activity.py                   # GmailFetchLog read-only
│   │   ├── bills.py                      # Bill list/detail/mark-paid
│   │   └── view_email.py                 # /api/email/messages/{id}/view (deep-link)
│   ├── services/
│   │   ├── oauth_service.py              # GmailOAuth class (separate from login GoogleOAuth)
│   │   ├── credential_vault.py           # Encrypt/decrypt refresh tokens
│   │   ├── access_token_cache.py         # Redis lookup + refresh
│   │   ├── scanner_service.py            # Per-credential scan orchestration
│   │   ├── classifier.py                 # Rule-based compliance detector (replaceable in v2.1)
│   │   ├── bill_extractor.py             # Bill metadata via LLM + regex fallback
│   │   ├── bill_service.py               # mark-as-paid + recurrence detection
│   │   └── ingestion_service.py          # Attachment → Document creation
│   ├── tasks/
│   │   └── scanner_task.py               # APScheduler-callable function
│   ├── mcp/
│   │   ├── server.py                     # FastMCP server instance + 6 @mcp.tool definitions
│   │   ├── tools.py                      # tool function bodies (audit + RLS context)
│   │   └── client.py                     # in-memory Client wrapper for Phase 12 agents
│   └── classifier_rules.py               # Sender-domain regex + subject keywords (DATA, swappable)
└── tasks/
    └── document_tasks.py                 # EXISTING — reused for attachment processing (no fork)
```

**Frontend structure (`frontend/src/app/dashboard/email/`):**

```
email/
├── connect/page.tsx                      # OAuth redirect launcher + connection status
├── settings/page.tsx                     # Filter rules CRUD
├── activity/page.tsx                     # GmailFetchLog three-state table
├── bills/page.tsx                        # Bill dashboard (cards + filter table + bulk-paid)
└── bills/[id]/page.tsx                   # Bill detail page
```

There is also an EXISTING `/oauth/callback/page.tsx` for login OAuth — **do NOT reuse it for Gmail credentials**. Login OAuth callback ends with the user signed in; Gmail OAuth callback ends with a `GmailCredential` row inserted and a redirect to `/dashboard/email/connect?status=success`. Implement a separate handler.

### Pattern 1: FastMCP server with in-memory client (RECOMMENDED — supersedes D-31 subprocess pattern)

**What:** A single FastMCP server instance lives in module scope; Phase 12 agents create an in-memory `Client` against it whenever they need to call a tool. No subprocess, no stdio pipes, no lifecycle conflicts with FastAPI lifespan.

**When to use:** All Phase 15 tool calls in v2.0 (Phase 12 agents share the FastAPI process).

**Example:**
```python
# backend/app/email/mcp/server.py
# Source: https://gofastmcp.com/clients/client (in-memory transport)
from fastmcp import FastMCP
from pydantic import BaseModel, Field

mcp = FastMCP(
    "Smart-Docs Gmail Tools",
    instructions="Read-only Gmail tools for internal compliance agents.",
)


class GmailSearchArgs(BaseModel):
    user_id: int = Field(description="Originating user id (for RLS context)")
    client_id: int = Field(description="Originating client id (for RLS context)")
    query: str = Field(description="Gmail search query (e.g. 'from:gst.gov.in newer_than:7d')")
    max_results: int = Field(default=50, ge=1, le=500)


@mcp.tool
def gmail_search(args: GmailSearchArgs) -> dict:
    """Search Gmail messages matching a query. Returns message IDs only."""
    from app.email.mcp.tools import gmail_search_impl
    return gmail_search_impl(args)
```

```python
# backend/app/email/mcp/client.py
from fastmcp import Client
from app.email.mcp.server import mcp

# Reusable in-memory client; safe across requests.
async def call_gmail_tool(tool_name: str, args: dict) -> dict:
    async with Client(mcp) as client:
        result = await client.call_tool(tool_name, args)
        return result.data
```

**Why this beats subprocess.Popen (D-31):** No stdio framing bugs, no orphan-process risk, no double-fork on container restart, no IPC serialization overhead, exceptions surface as native Python exceptions in the caller (not parsed from stderr). Phase 12 agents call `await call_gmail_tool("gmail_search", {...})`. Audit + RLS context are set inside `gmail_search_impl()` before any DB read.

### Pattern 2: FastMCP with stdio + subprocess.Popen (only if D-31 is held firm)

**What:** Backend FastAPI app spawns the MCP server as a child via `subprocess.Popen(["python", "-m", "app.email.mcp.server"], stdin=PIPE, stdout=PIPE)` in a `lifespan` handler. The parent backend then connects via the FastMCP `Client(transport=StdioTransport(stdin, stdout))` pattern.

**When to use:** Only if v2.1 plans to move Phase 12 agents to a separate OS process and you want to lock the IPC contract NOW. Otherwise this is over-engineering.

**Example (lifespan handler — NEW pattern; main.py currently has no lifespan):**
```python
# backend/app/main.py — modification
from contextlib import asynccontextmanager
import subprocess, sys, os

@asynccontextmanager
async def lifespan(app: FastAPI):
    mcp_proc = subprocess.Popen(
        [sys.executable, "-m", "app.email.mcp.server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        env={**os.environ},          # share DATABASE_URL, FERNET_KEY, etc.
        bufsize=0,                    # critical for stdio framing
    )
    app.state.mcp_proc = mcp_proc
    try:
        yield
    finally:
        if mcp_proc.poll() is None:
            mcp_proc.terminate()
            try:
                mcp_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                mcp_proc.kill()

app = FastAPI(lifespan=lifespan, ...)
```

**Pitfall:** A bad audit/log line written to stdout instead of stderr will corrupt the JSON-RPC stream. All FastMCP child processes MUST log to stderr or to a file — never stdout. The current `app.compliance.services.scheduler` uses `logging.getLogger(__name__)` which inherits root logger config; verify the root logger is not writing to stdout in the MCP child.

### Pattern 3: Gmail OAuth web-server flow with `access_type=offline` (REQUIRED)

**What:** Two-step flow — frontend hits `/api/email/gmail/oauth/authorize` → backend returns Google authorization URL with `state` (signed JWT for CSRF) → user consents on Google → Google redirects to `/api/email/gmail/oauth/callback?code=...&state=...` → backend exchanges code for tokens → stores refresh token Fernet-encrypted.

**When to use:** EMAIL-01 — every new Gmail connection.

**Example:**
```python
# backend/app/email/services/oauth_service.py
# Source: https://developers.google.com/identity/protocols/oauth2/web-server
from urllib.parse import urlencode

class GmailOAuth:
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",
    ]

    @staticmethod
    def get_auth_url(state: str, redirect_uri: str) -> str:
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,         # CAN reuse same client_id as login OAuth
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(GmailOAuth.SCOPES),
            "access_type": "offline",                       # CRITICAL — gets refresh_token
            "prompt": "consent",                            # CRITICAL — forces refresh_token even on re-consent
            "include_granted_scopes": "true",               # carry-over previously granted scopes
            "state": state,
        }
        return f"{GmailOAuth.AUTH_URL}?{urlencode(params)}"
```

**Critical:** Without `prompt=consent`, Google may NOT return a refresh token on subsequent re-authorizations from the same user — the user has already consented and Google considers the previous refresh token canonical. With `prompt=consent` you force the consent screen and reliably get a fresh refresh token every time.

### Pattern 4: APScheduler per-credential job persistence

**What:** Each active `GmailCredential` row corresponds to one APScheduler job with `id=f"gmail_scan_{credential_id}"`, `trigger=IntervalTrigger(minutes=cadence_minutes)`. Jobs persist in the existing `apscheduler_jobs` table (Phase 11 SQLAlchemyJobStore). When a credential is created, updated, or deleted, the corresponding job is added/replaced/removed.

**When to use:** EMAIL-04 cadence rules + EMAIL-08 deduplication run inside the job body.

**Example:**
```python
# backend/app/email/services/scanner_service.py
# Source: app/compliance/services/scheduler.py existing pattern
from apscheduler.triggers.interval import IntervalTrigger
from app.compliance.services.scheduler import get_scheduler

def schedule_gmail_scan(credential_id: int, cadence_minutes: int) -> None:
    sched = get_scheduler()
    if sched is None:
        return
    sched.add_job(
        func="app.email.tasks.scanner_task:run_scan",   # importable string for cross-process
        trigger=IntervalTrigger(minutes=cadence_minutes),
        args=[credential_id],
        id=f"gmail_scan_{credential_id}",
        replace_existing=True,
        misfire_grace_time=300,
        coalesce=True,                                   # collapse missed runs into one
    )
```

**Phase 11 lesson re-applied (CRIT-2 second pass):** The scan task body MUST set tenant context via `set_tenant_context_for_celery(client_id=credential.client_id, user_id=credential.user_id, cross_mode=False)` BEFORE any DB read. APScheduler runs in the FastAPI process and inherits NO request context — RLS will fail-closed and silently no-op without this line. Mirror the pattern at `app/compliance/services/scheduler.py:185`.

### Pattern 5: Gmail incremental sync via `historyId` (recommended for v2.0)

**What:** First scan does a full `messages.list(q="…")` and stores `historyId` from the latest message. Subsequent scans pass `startHistoryId` to `users.history.list()` and only process new messages. Falls back to full sync on 404 (history aged out, typically >7 days unused).

**When to use:** Reduces Gmail quota by ~50× compared to full re-scan every 15 minutes. `history.list` costs 2 quota units vs `messages.list` at 5 — small win — but each `messages.list` returns at best 500 IDs, then a `messages.get` per ID at 20 quota each. With history, you only fetch the deltas.

**Example:**
```python
# backend/app/email/tasks/scanner_task.py
# Source: https://developers.google.com/gmail/api/guides/sync
def run_scan(credential_id: int) -> None:
    creds = load_credentials(credential_id)
    service = build("gmail", "v1", credentials=creds)
    last_history_id = creds.last_history_id  # column on GmailCredential

    if last_history_id is None:
        # First-ever scan — full
        messages = full_scan(service, query=build_query(creds))
        new_history_id = messages[0].historyId if messages else None
    else:
        try:
            history = service.users().history().list(
                userId="me",
                startHistoryId=last_history_id,
                historyTypes=["messageAdded"],
            ).execute()
            messages = [h for r in history.get("history", []) for h in r.get("messagesAdded", [])]
            new_history_id = history.get("historyId")
        except HttpError as e:
            if e.resp.status == 404:
                # historyId aged out — fall back to full
                messages = full_scan(service, query=build_query(creds))
                new_history_id = messages[0].historyId if messages else None
            else:
                raise
    # ... process messages, update GmailCredential.last_history_id ...
```

### Pattern 6: Hybrid Bill model with optional `source_document_id` (D-19 refined)

**What:** `bills.source_document_id` is `nullable=True`. Bills with a PDF attachment populate it; text-only bills (no attachment) leave it NULL. Recurring-bill detection joins on `bills.parent_bill_id`.

**When to use:** Every bill row.

**Example (Alembic migration excerpt):**
```python
# backend/alembic/versions/0025_phase15_email_credentials_bills.py
op.create_table(
    "bills",
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("client_id", sa.Integer, sa.ForeignKey("compliance_clients.id", ondelete="CASCADE"), nullable=False),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    sa.Column("biller_name", sa.String(255), nullable=False),
    sa.Column("biller_name_normalized", sa.String(255), nullable=False),
    sa.Column("biller_category", sa.String(30), nullable=False),       # CHECK constraint: utility|telecom|credit_card|subscription|other
    sa.Column("amount_due", sa.Numeric(14, 2), nullable=False),
    sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
    sa.Column("due_date", sa.Date, nullable=True),
    sa.Column("account_number_last4", sa.String(4), nullable=True),
    sa.Column("payment_status", sa.String(20), nullable=False, server_default="pending"),
    sa.Column("is_recurring", sa.Boolean, nullable=False, server_default=sa.text("false")),
    sa.Column("recurrence_period", sa.String(20), nullable=True),       # monthly|quarterly|annual|null
    sa.Column("parent_bill_id", sa.Integer, sa.ForeignKey("bills.id", ondelete="SET NULL"), nullable=True),
    sa.Column("source_document_id", sa.Integer, sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),  # D-19
    sa.Column("source_email_id", sa.Integer, sa.ForeignKey("gmail_message_log.id", ondelete="SET NULL"), nullable=True),
    sa.Column("payment_date", sa.Date, nullable=True),
    sa.Column("payment_reference", sa.String(255), nullable=True),
    sa.Column("payment_method", sa.String(20), nullable=True),
    sa.Column("extraction_prompt_rev", sa.String(20), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
)

# Partial unique index for recurrence detection — only enforces when account_number_last4 is set
op.create_index(
    "ux_bills_recurrence_key",
    "bills",
    ["client_id", "biller_name_normalized", "account_number_last4"],
    unique=True,
    postgresql_where=sa.text("account_number_last4 IS NOT NULL"),
)
```

### Anti-Patterns to Avoid

- **Custom Gmail polling loop with `httpx`:** Skips google-api-python-client's built-in 429 retry, batch helpers, pagination. Builds throw-away code.
- **Storing access tokens in DB:** Adds attack surface; tokens expire in ~1 hour anyway. Redis-cache them with TTL or derive on each call.
- **Writing email body to a column "for debugging":** Violates D-34 fetch-once-discard. Even a TEXT column "for incident triage" leaves PII at rest.
- **Bypassing audit log for "performance":** Phase 9 made audit immutable for a reason. Audit failures fall back to JSONL on disk per `_append_audit_failure_fallback()` — never silenced.
- **Coupling bill-detection to compliance-notice classifier:** They share regex patterns but are independent code paths. Mixing them turns one ML upgrade into two.
- **Generic "email provider" abstraction in v2.0:** Outlook/Yahoo/IMAP are Phase 14's domain. Building generic now creates pre-mature abstraction.
- **Reading `localStorage.getItem("access_token")` in any new frontend code:** The token is in a js-cookie named `"token"` (verified at `frontend/src/lib/api.ts:39`). Existing `useNotificationStream.ts:43` is the broken pattern; do NOT replicate it. Read via `Cookies.get("token")` from `js-cookie`.
- **Using login `GoogleOAuth` class in `app/services/oauth_service.py:14` for Gmail credentials:** Scopes diverge (`openid email profile` vs `gmail.readonly + gmail.modify`); side-effect (creating a User row) is wrong. Add a separate `GmailOAuth` class.
- **Caching email bodies in Redis "for replay":** Even with 1-minute TTL it's PII at rest. D-34 forbids it.
- **Forgetting to set RLS context inside APScheduler-spawned scan jobs:** Same CRIT-2 pattern Phase 11 hit. Without `set_config('app.current_client_id', credential.client_id)` before any tenant-scoped query, RLS fails closed and the scanner silently no-ops.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MCP protocol envelope | Custom JSON-RPC parser, manual stdio framing | FastMCP 3.2.4 | Spec drift, capability negotiation, schema generation, error envelope — all handled. |
| Gmail OAuth refresh | Hand-rolled token refresh with httpx | `google.oauth2.credentials.Credentials.refresh()` | Built-in `RefreshError` on `invalid_grant`; clock-skew handling; threadsafe. |
| Gmail message pagination | Loop manually checking `nextPageToken` | `googleapiclient.discovery.build("gmail", "v1").users().messages().list_next()` | Correctly chains pagination; handles edge cases. |
| Rate-limit retry | Custom exponential backoff | `googleapiclient` built-in retry on 429/500/503 | Already implements 1-2-4-8s backoff. |
| Fernet symmetric encryption | Build crypto from `cryptography` primitives | `app.compliance.utils.pii_encryption.encrypt_field` | INFRA-06 ships `MultiFernet` rotation, lru-cached cipher, `BYTEA`-suitable bytes return type. |
| LLM prompt fallback | Build new provider chain | `app.services.llm_service.extract_with_llm(text, "bills")` | Phase 5 built a 5-provider chain (Ollama → Gemini → Anthropic → OpenAI → regex). Already returns a `degraded_local_fallback` boolean. |
| APScheduler durable job storage | DIY cron with database polling | Phase 11 `apscheduler_jobs` table + `SQLAlchemyJobStore` | Survives restarts; replace_existing makes job upsert atomic. |
| RLS tenant context | Hand-write `set_config` calls everywhere | Existing `set_tenant_context_for_celery(client_id, user_id, cross_mode)` | One function; same bug surface as Phase 9/10/11 — don't fork. |
| Audit log write | Inline INSERT into audit_logs | `app.services.audit_service.log_audit_event_strict` | Returns False on failure but ALSO appends to dead-letter JSONL; ERROR-level on failure. |
| OAuth CSRF state | Cookie-based session tracking | Signed JWT with `nonce` + 10-minute exp (existing pattern at `auth.py:309-315`) | Stateless; survives cross-origin redirects; no Redis needed. |
| Gmail attachment filename heuristics | Sniff MIME from filename | `magic_bytes` validation in `app.services.storage_service.validate_magic_bytes` | Existing function checks PDF/PNG/JPG/TIFF/DOCX magic bytes; reuse. |

**Key insight:** Eight of the ten "deceptively complex" pieces of this phase are already built into INFRA-06/07, the v1.0 LLM service, the v1.0 storage service, the Phase 11 scheduler, and the existing `audit_service`. Phase 15's net-new code is the GmailCredential vault, the rule classifier, the bill model, the 6 MCP tools, and the frontend route tree — everything else is reuse.

## Runtime State Inventory

> Phase 15 is greenfield (additive tables + new code paths) — there is no rename or refactor of existing runtime state.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — all Phase 15 tables (`gmail_credentials`, `gmail_filter_rules`, `gmail_message_log`, `gmail_fetch_log`, `bills`) are NEW. No existing rows to migrate. | None |
| Live service config | None — Google OAuth client may need new "Authorized redirect URI" registered (`${BASE_URL}/api/email/gmail/oauth/callback`). The existing login redirect `${BACKEND_URL}/api/auth/callback/google` already exists but is unrelated. | Operator action: add the new redirect URI in Google Cloud Console BEFORE deploy. |
| OS-registered state | APScheduler jobs persisted in `apscheduler_jobs` table — Phase 15 adds new job rows on credential connect. No OS-level changes (no systemd / Task Scheduler / launchd). | None — automatic via `add_job(replace_existing=True)`. |
| Secrets and env vars | NEW env vars required: `GMAIL_OAUTH_REDIRECT_URI` (or derive from `BASE_URL`). REUSE existing: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (already used by login OAuth), `FERNET_KEY` (Phase 9 INFRA-06), `REDIS_URL`, `DATABASE_URL`. | Operator action: register `GMAIL_OAUTH_REDIRECT_URI` in `.env` and Vercel/Render dashboards. |
| Build artifacts / installed packages | NEW pip dependencies — `fastmcp`, `google-api-python-client`, `google-auth-oauthlib`. Add to `backend/requirements.txt`. Docker image rebuild required. | Build action: `pip install -r requirements.txt` after merge; Docker image rebuild. |

## Common Pitfalls

### Pitfall 1: D-31 subprocess.Popen vs FastMCP transport semantics

**What goes wrong:** D-31 says "backend entrypoint spawns child via subprocess.Popen", but FastMCP's stdio transport is designed for **the client to spawn the server** (Claude Desktop pattern). If the parent FastAPI process spawns the MCP child, the parent must ALSO act as MCP client — which means managing stdio framing, JSON-RPC over pipes, child process lifecycle, restart logic, and stderr-vs-stdout discipline.

**Why it happens:** The decision was made before checking the FastMCP transport model. FastMCP's three transports are: (a) stdio — client launches server, (b) http/streamable-http — server is a long-lived ASGI app, (c) **in-memory** — server and client live in the same Python process.

**How to avoid:** **Use in-memory transport.** Phase 12 agents and the Gmail MCP server share the same Python process; in-memory means `Client(mcp_server_instance)` directly invokes tool functions with full type-checked args, native exception propagation, and zero IPC. Subprocess + stdio adds zero security and several failure modes. Document the v2.1 swap path: if Phase 12 agents become out-of-process (separate container or remote), swap to streamable-http transport with auth — also a one-file change.

**Warning signs:** Tests for the MCP child process require background spawning + signal handling + read/write timeouts. CI flakes from races between parent kill and child exit.

### Pitfall 2: Token refresh race + invalid_grant detection

**What goes wrong:** Two scanner jobs running for the same credential trigger token refresh simultaneously. One succeeds and writes to Redis; the other gets `invalid_grant` because Google may have rotated the refresh token on the first call.

**Why it happens:** Per Google's OAuth docs, refresh tokens *can* be rotated when used (silent rotation). Two concurrent uses race.

**How to avoid:** Use `replace_existing=True` + `coalesce=True` on APScheduler `add_job` — collapses missed runs. Add a Redis distributed lock keyed on `gmail:scan_lock:{credential_id}` with 5-minute TTL around the entire scan body. If lock cannot be acquired, log skipped run as `SUCCESS_EMPTY` (no fetch failure — it's just deduped).

**Warning signs:** Sporadic `RefreshError: invalid_grant` in production logs but the user hasn't actually revoked access; the credential row gets prematurely marked REVOKED.

### Pitfall 3: gmail_message_id collision across users

**What goes wrong:** A scan run writes a `gmail_message_log` row keyed only on `gmail_message_id`. Two users in two different households both received the same Gmail message ID (statistically impossible, but the schema must encode the invariant correctly).

**Why it happens:** Gmail message IDs are globally unique within a user's mailbox, NOT globally unique across all of Gmail.

**How to avoid:** UNIQUE constraint on `(credential_id, gmail_message_id)`, NOT on `gmail_message_id` alone. (D-13 already says this — verify the migration encodes it correctly.) Add a CHECK that `credential_id` is NOT NULL before constraint creation.

**Warning signs:** Test fixture creating two credentials with the same fake `gmail_message_id="abc"` fails with IntegrityError on the second insert when it should succeed.

### Pitfall 4: gmail.modify scope is restricted — verification required

**What goes wrong:** `gmail.readonly` and `gmail.modify` are both **restricted scopes** under Google's OAuth verification policy. Apps that store data on servers (Phase 15 stores email IDs + metadata + Fernet-encrypted refresh tokens) require a security assessment and may need brand verification before production launch.

**Why it happens:** Google's policy applies to all apps requesting restricted scopes regardless of internal use; the verification process can take 4-8 weeks for first-time apps.

**How to avoid:** Submit OAuth verification request to Google early — well before phase ships. The app may operate in "Testing" mode for up to 100 users with refresh tokens that expire after **7 days**, which is fine for staging but requires verification for production. Document this as a pre-launch dependency in PROJECT.md.

**Warning signs:** Refresh tokens silently expire 7 days after issuance during early-access pilot; users report "reconnect required" repeatedly.

### Pitfall 5: spaCy NER is `NotImplementedError` — D-17 is broken

**What goes wrong:** D-17 says "Notice metadata extraction reuses Phase 10 spaCy NER — same code path." But `app/ml/compliance/ner.py:49` raises `NotImplementedError("spaCy custom NER not yet trained")`. Phase 10 v2.0 shipped only the rule-based scorer + regex_patterns; the custom NER pipeline was deferred to v2.1 (per `STATE.md` "v2.1 deferral commit").

**Why it happens:** D-17 was written assuming Phase 10's CLASS-05 (spaCy NER) shipped. It did not.

**How to avoid:** v2.0 path uses **regex-only extraction** for compliance notices created from Gmail. The existing `regex_patterns.py` already extracts: GSTIN, PAN, CIN, DIN, section references (u/s 143(2)), GST notice numbers (DRC/ASMT/REG/RFD), IT notice sections (143/142/156/245/271/144/148). Combined with the LLM extraction service for narrative fields (`deadline`, `penalty_amount`, `tax_demand`), this covers ~80% of the v2.0 ComplianceNotice creation needs without spaCy. Document v2.1 swap path: when `app.ml.compliance.ner.extract()` is implemented, replace the regex-only pass with a regex-then-NER pass — one-file swap mirroring D-16's BERT pattern.

**Warning signs:** Calling the (currently NotImplementedError) NER extract function during a Gmail scan crashes the scanner job; planner unaware that NER isn't shipped.

### Pitfall 6: APScheduler job inherits no tenant context (CRIT-2 pattern repeats)

**What goes wrong:** A scanner job runs successfully but writes zero rows because every tenant-scoped query hits an empty RLS context and returns no rows.

**Why it happens:** APScheduler runs jobs in the FastAPI process but OUTSIDE any HTTP request — `TenantContextMiddleware` does NOT execute. ContextVars are empty. `is_local=false` `set_config` calls in the job body are required.

**How to avoid:** Mirror `app/compliance/services/scheduler.py:185` exactly: call `set_tenant_context_for_celery(client_id=None, user_id=None, cross_mode=True)` first to look up the credential, then `set_tenant_context_for_celery(client_id=cred.client_id, user_id=cred.user_id, cross_mode=False)` to scope subsequent reads.

**Warning signs:** Scanner runs, log says "completed", but no `gmail_message_log` rows were inserted.

### Pitfall 7: Forgetting `prompt=consent` returns no refresh token on re-auth

**What goes wrong:** User connects Gmail, then later disconnects and re-connects. The second OAuth round returns ONLY an access token, no refresh token. Scanner can't operate.

**Why it happens:** Without `prompt=consent`, Google considers the prior consent valid and only returns a new refresh token if the user revoked access between rounds.

**How to avoid:** Always pass `prompt=consent` to the authorization URL. Force the consent screen on every connection.

**Warning signs:** Reconnection silently produces a credential row with NULL `refresh_token_enc`. Scanner immediately fails on first run.

### Pitfall 8: Bills with no `account_number_last4` falsely link as recurring

**What goes wrong:** Two unrelated bills from the same biller (e.g., two different family members on Tata Power) both have `account_number_last4=NULL` because the bill body didn't contain it. The recurrence-detection unique constraint treats them as the same series.

**Why it happens:** A naive UNIQUE on `(client_id, biller_name_normalized, account_number_last4)` fires when account_number is NULL on both — UNIQUE treats NULLs as distinct in PostgreSQL by default, so the two bills don't conflict, but the recurrence-link query then matches them together.

**How to avoid:** Use a **partial unique index** with `WHERE account_number_last4 IS NOT NULL` (already in Pattern 6 above). Bills without account numbers do NOT participate in recurrence linking.

**Warning signs:** Manual test: create two bills from `Tata Power` with no account number → recurrence detection should NOT link them as parent/child.

### Pitfall 9: Gmail body fetched repeatedly across MCP tools

**What goes wrong:** Phase 12 agent calls `gmail_search`, then `gmail_read_message`, then `gmail_list_attachments`, then `gmail_get_attachment`. Each tool call fetches the body via `messages.get(format="full")` — 4× the quota cost AND 4× the audit log volume AND 4× the PII surface.

**Why it happens:** Tool design without thinking about call sequences.

**How to avoid:** D-34 says fetch-once-discard inside the **scanner** — re-affirm this for **MCP tools**: `gmail_read_message` returns body content, `gmail_list_attachments` returns metadata only (size, filename, attachment_id) without re-fetching the body, `gmail_get_attachment` uses the `messages.attachments.get` endpoint (separate from `messages.get`). Inside scanner, body lives in a local Python variable across classification + extraction + bill_extractor calls.

**Warning signs:** Audit log shows three `MCP_TOOL_CALL` rows with the same `body_sha256` for the same message_id — duplicate fetches.

### Pitfall 10: Existing httpOnly-cookie claim in CONTEXT.md is inaccurate

**What goes wrong:** CONTEXT.md (line 164) says "JWT now in httpOnly cookies; localStorage-read pattern is broken." That's the DESIRED end state — but the actual code uses `js-cookie` (JavaScript-readable, NOT httpOnly) at `frontend/src/lib/api.ts:39` and stores the token in cookie name `"token"`. The `useNotificationStream.ts:43` `localStorage.getItem("access_token")` line IS broken (different key, different storage), but it's broken because the token is in `Cookies.get("token")`, not because cookies are httpOnly.

**Why it happens:** CONTEXT.md author misread the code path; the fix was tracked but not applied, OR there are two Phase 11 issues conflated.

**How to avoid:** All new frontend code should use `Cookies.get("token")` from `js-cookie` (matching `lib/api.ts:39`). The OAuth callback page already uses the AuthContext setter `setTokensFromOAuth()` which writes via `Cookies.set("token", ...)` at `AuthContext.tsx:52` — Phase 15 OAuth callback for Gmail does NOT need to set this (the user is already authenticated; the OAuth flow only adds a Gmail credential).

**Warning signs:** New code reading `localStorage.getItem("access_token")`. Or new code attempting `document.cookie` parsing manually.

## Code Examples

### gmail_search MCP tool implementation (verified pattern)

```python
# backend/app/email/mcp/tools.py
# Sources: https://gofastmcp.com/servers/tools (error handling), 
#          https://googleapis.github.io/google-api-python-client/docs/dyn/gmail_v1.users.messages.html (API)
import hashlib
from fastmcp.exceptions import ToolError
from googleapiclient.errors import HttpError

from app.email.mcp.server import GmailSearchArgs
from app.email.services.access_token_cache import get_or_refresh_access_token
from app.compliance.middleware.tenant_context import set_tenant_context_for_celery
from app.services.audit_service import log_audit_event_strict


def gmail_search_impl(args: GmailSearchArgs) -> dict:
    set_tenant_context_for_celery(
        client_id=args.client_id, user_id=args.user_id, cross_mode=False
    )
    creds = get_or_refresh_access_token(args.client_id, args.user_id)
    service = build("gmail", "v1", credentials=creds)
    try:
        resp = service.users().messages().list(
            userId="me", q=args.query, maxResults=args.max_results,
        ).execute()
    except HttpError as e:
        if e.resp.status == 401:
            raise ToolError("Gmail credential is invalid; user must reconnect.")
        if e.resp.status in (429, 500, 503):
            # google-api-python-client retries automatically; if it surfaces, give up
            raise ToolError("Gmail rate limit exceeded; retry in 60 seconds.")
        raise

    message_ids = [m["id"] for m in resp.get("messages", [])]
    log_audit_event_strict(
        user_id=args.user_id,
        action="MCP_TOOL_CALL",
        resource_type="gmail_tool",
        resource_id=None,
        details={
            "tool": "gmail_search",
            "client_id": args.client_id,
            "query_sha256": hashlib.sha256(args.query.encode()).hexdigest(),  # PII redaction (D-36)
            "result_count": len(message_ids),
        },
    )
    return {"message_ids": message_ids, "next_page_token": resp.get("nextPageToken")}
```

### Rule-based compliance detector (D-16 v2.0; one-file v2.1 swap path)

```python
# backend/app/email/services/classifier.py
# Source: D-16 revised; Phase 10 v2.0 ships rule-based, BERT in v2.1
import re

# Indian regulatory authority sender domains. Curated 2026-05-07 from
# https://web.guidelines.gov.in/2-2-government-domains and ministry portals.
# Operator-tunable via gmail_filter_rules so this list is the seed default only.
COMPLIANCE_SENDER_PATTERNS = [
    re.compile(r"@([a-z]+\.)?gov\.in$", re.IGNORECASE),     # all gov.in (including state subdomains)
    re.compile(r"@([a-z]+\.)?nic\.in$", re.IGNORECASE),     # NIC-hosted (some IT/MCA emails)
    re.compile(r"@cbic-gst\.gov\.in$", re.IGNORECASE),       # GST/CBIC
    re.compile(r"@incometax\.gov\.in$", re.IGNORECASE),      # Income Tax
    re.compile(r"@incometaxindiaefiling\.gov\.in$", re.IGNORECASE),
    re.compile(r"@mca\.gov\.in$", re.IGNORECASE),
    re.compile(r"@sebi\.gov\.in$", re.IGNORECASE),
    re.compile(r"@rbi\.org\.in$", re.IGNORECASE),            # NOTE: RBI is .org.in (per CONTEXT.md typo)
    re.compile(r"@epfindia\.gov\.in$", re.IGNORECASE),
    re.compile(r"@esic\.in$", re.IGNORECASE),
]

# High-precision keywords; designed for low false-positive rate.
COMPLIANCE_SUBJECT_KEYWORDS = re.compile(
    r"\b(notice|intimation|demand|scrutiny|show.cause|adjudication|"
    r"assessment\s*order|penalty|hearing|summons|inquiry)\b",
    re.IGNORECASE,
)


def classify(sender: str, subject: str) -> tuple[bool, float]:
    """Returns (is_compliance_notice, confidence).

    Binary in v2.0:
      - sender matches gov.in pattern AND subject matches keyword → (True, 1.0)
      - sender matches BUT subject doesn't → (False, 0.5) → routed to review queue
      - subject matches BUT sender doesn't (forwarded) → (False, 0.0) → dms_only per D-33
      - neither matches → (False, 0.0) → ignored
    """
    sender_match = any(p.search(sender) for p in COMPLIANCE_SENDER_PATTERNS)
    subject_match = bool(COMPLIANCE_SUBJECT_KEYWORDS.search(subject))
    if sender_match and subject_match:
        return True, 1.0
    if sender_match and not subject_match:
        return False, 0.5  # uncertain; review queue
    return False, 0.0
```

**v2.1 swap path:** Replace `classify()` with a function that calls a BERT classifier; signature stays `(sender: str, subject: str, body: str | None = None) -> tuple[bool, float]`; the rest of the pipeline is unchanged.

### Bill extraction prompt template

```python
# backend/app/email/services/bill_extractor.py
# Source: extends app/services/llm_service.py with bill-specific prompt
from app.services.llm_service import extract_with_llm

EXTRACTION_PROMPT_REV = "1.0.0"


def extract_bill(body_text: str, sender_domain: str) -> dict:
    # Reuse the v1.0 LLM service category="bills" — already configured to extract:
    #   bill_number, billing_date, due_date, total_amount, vendor, account_number
    result = extract_with_llm(body_text, "bills")
    fields = result.get("fields", {})
    biller = fields.get("vendor", {}).get("value") or _infer_biller_from_domain(sender_domain)
    amount_due = fields.get("total_amount", {}).get("value")
    due_date = fields.get("due_date", {}).get("value")
    account_no = fields.get("account_number", {}).get("value", "")
    return {
        "biller_name": biller,
        "amount_due": amount_due,
        "due_date": due_date,
        "account_number_last4": account_no[-4:] if account_no else None,
        "extraction_prompt_rev": EXTRACTION_PROMPT_REV,
        "extraction_provider": result.get("provider"),
        "degraded_local_fallback": result.get("degraded_local_fallback", False),
    }
```

### OAuth callback handler (frontend identity via httpOnly-token-in-cookie pattern)

```python
# backend/app/email/routers/oauth.py
# Source: extends app/routers/auth.py:319-435 pattern
@router.get("/oauth/callback")
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def gmail_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),                  # MUST be authenticated
    client_id: int = Depends(get_active_client_id),          # MUST have an active client
):
    if error:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/dashboard/email/connect?error=oauth_denied")
    if not code:
        raise HTTPException(400, "Missing authorization code")
    if not state:
        raise HTTPException(400, "Missing OAuth state")
    try:
        jwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(400, "OAuth state expired")
    except jwt.InvalidTokenError:
        raise HTTPException(400, "Invalid OAuth state")
    
    token_data = await GmailOAuth.exchange_code(code, redirect_uri=settings.GMAIL_OAUTH_REDIRECT_URI)
    if "refresh_token" not in token_data:
        # User pre-authorized without prompt=consent OR Google rotated; either way, treat as failure
        raise HTTPException(400, "No refresh token returned; please disconnect and reconnect.")
    
    cred = save_credential(
        db, user_id=user.id, client_id=client_id,
        refresh_token=token_data["refresh_token"],            # encrypted in save_credential
        scopes=token_data.get("scope"),
        google_account_email=token_data.get("id_token") and decode_id_token(...).get("email"),
    )
    schedule_gmail_scan(cred.id, cadence_minutes=15)
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/dashboard/email/connect?status=success&credential_id={cred.id}")
```

**Critical:** This callback REQUIRES the user to already be authenticated (cookie-based session via `Depends(get_current_user)`). The Gmail OAuth flow is "add a credential to my account" — the user must be logged in. The CSRF protection is a JWT in `state`. The frontend kicks off the flow by hitting `/api/email/gmail/oauth/authorize`, which requires `Depends(get_current_user)` and includes the user's auth cookie. The redirect to Google preserves the user identity through the JWT state.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Raw `mcp` SDK with manual `Server()` + `setRequestHandler` | FastMCP `@mcp.tool` decorator | FastMCP 1.0 absorbed into mcp SDK 2024 | ~5x less boilerplate; auto-schema generation. |
| HTTP/SSE only for MCP | stdio + streamable-http + **in-memory** | FastMCP 2.0+ (2025) | In-memory transport is the right choice for embedded MCP — no subprocess overhead. |
| `messages.list` re-fetch every poll | `history.list` with `startHistoryId` | Gmail API since v1 launch | ~50× quota reduction for 15-minute polling. |
| `@app.on_event("startup")` | `lifespan=...` parameter | FastAPI 0.93+ (2023) | Required for clean async resource management; deprecated decorator still works but spawns warnings. |
| Polling Gmail every 15 min via cron | APScheduler durable jobstore | Phase 11 chose APScheduler; Gmail API itself supports push (Pub/Sub) but requires GCP project + topic — out of scope v2.0 | Push notifications deferred to v3.0. |

**Deprecated/outdated:**
- `mail.google.com/` scope (full mailbox): Restricted, never use; `gmail.modify` is sufficient for label-only writes per D-02.
- `users.messages.send`: Out of scope (D-03). Don't request `gmail.send`.
- `flask-style` Server-Sent Events for MCP: Deprecated; use streamable-http instead.

## Open Questions

1. **D-31 subprocess.Popen vs in-memory transport — REVISIT REQUIRED**
   - What we know: FastMCP supports stdio (client-spawns-server), streamable-http, and in-memory. In-memory eliminates subprocess + IPC for same-process consumers.
   - What's unclear: Was D-31 intended to support out-of-process Phase 12 agents (which v2.0 does not have)?
   - Recommendation: Planner explicitly compares the two transport choices and picks one. Default recommendation: in-memory.

2. **Google OAuth verification timing**
   - What we know: `gmail.readonly` and `gmail.modify` are restricted; security assessment may be required.
   - What's unclear: Has the org submitted OAuth verification? Will pilot users hit the 7-day refresh-token expiration in Testing mode?
   - Recommendation: File OAuth verification request as a parallel-track plan task; document a 100-user, 7-day-token Testing-mode launch path so pilot can start without verification complete.

3. **Number of Phase 12 agents and their MCP call patterns**
   - What we know: D-28 says agent identity inherits from user; tool args carry user_id + client_id.
   - What's unclear: Will Phase 12 agents make ~10 MCP calls per response or ~100? The audit log volumetrics depend on this — the difference is 1k vs 10k audit_log rows per active credential per day.
   - Recommendation: Plan for the high-volume case; the audit_log immutability triggers + dead-letter file are already in place.

4. **Bill detail page deep-link to source email**
   - What we know: D-37 says bill detail has a "View source email" link via MCP `gmail_read_message` — but viewing email body via a backend endpoint means the audit log will record a `MCP_TOOL_CALL` for the human user (not an agent). That's good for traceability but increases per-user audit volume.
   - What's unclear: Is the bill detail page showing email body inline, or does the user click a button to fetch on demand?
   - Recommendation: On-demand fetch (button click) → one audit row per intentional view → minimal PII surface.

5. **Filter-rule precedence when multiple rules match**
   - What we know: D-11 stores `(sender_pattern, subject_pattern, label_include, label_exclude, route_to)`.
   - What's unclear: If two rules match the same email, which `route_to` wins?
   - Recommendation: Add a `priority` integer column; lower number = higher priority. Document the precedence rule in the CRUD docs.

6. **Deduplication across `dms_only` and `bill` and `compliance_notice` routes**
   - What we know: D-13 says (credential_id, gmail_message_id) is UNIQUE.
   - What's unclear: If a bill email is also a compliance notice (rare but possible — say, late TDS payment notice that also acts as a payable bill), does it get one row in `bills` AND one in `compliance_notices`?
   - Recommendation: Yes — one `gmail_message_log` row, optionally referenced from BOTH `bills.source_email_id` AND `compliance_notices.source_email_id`. The `gmail_message_log` is the single point of dedup.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | All Phase 15 code | ✓ (project requires-python = >=3.12) | 3.12+ | — |
| PostgreSQL 14+ with RLS | All tables | ✓ (existing) | 14+ | — |
| Redis | Access-token cache, distributed scan-lock | ✓ (existing in `requirements.txt:54`) | 5.0.1 client | — |
| `cryptography` (Fernet) | Refresh-token encryption (INFRA-06 reuse) | ✓ (transitive via existing requirements; pii_encryption.py uses it) | (transitive) | None — required |
| `apscheduler` | Per-credential scan job persistence | ✓ (existing in `requirements.txt:42`) | 3.11.0 | None — required |
| `httpx` | OAuth token exchange (existing pattern) | ✓ (existing in `requirements.txt:65`) | 0.25.2 | — |
| `fastmcp` | MCP server library | ✗ (NEW) | 3.2.4 (PyPI) | None — required for D-29 |
| `google-api-python-client` | Gmail API | ✗ (NEW) | 2.196.0 (PyPI) | Direct httpx (NOT recommended; see Don't Hand-Roll) |
| `google-auth-oauthlib` | OAuth flow helper | ✗ (NEW) | 1.4.0 (PyPI) | Manual flow with httpx (existing oauth_service pattern) |
| Google Cloud Project + OAuth client | OAuth + Gmail API | ✓ (already exists for login OAuth) | — | — |
| Google Cloud OAuth verification (gmail.readonly + gmail.modify restricted scopes) | Production launch | ⚠ TBD | — | Testing mode (100 users, 7-day refresh tokens) — sufficient for early-access pilot |
| GCP project quota | Default 80M units/day = effectively unlimited for 100-user pilot | ✓ | — | — |
| Existing Phase 9 INFRA-06 Fernet helper | Refresh-token encryption | ✓ at `app/compliance/utils/pii_encryption.py` | — | — |
| Existing Phase 9 `require_compliance_permission` factory | RBAC gate on routers | ✓ at `app/utils/security.py:161` | — | — |
| Existing Phase 9 audit_log + immutability triggers | MCP_TOOL_CALL audit rows | ✓ at `app/services/audit_service.py:85` (log_audit_event_strict at :137) | — | — |
| Existing Phase 9 RLS context middleware | Per-request tenant isolation | ✓ at `app/compliance/middleware/tenant_context.py` | — | — |
| Existing Phase 10 `enqueue_low_confidence` | Route low-confidence detector results to review queue | ✓ at `app/compliance/services/review_queue_service.py:72` | — | — |
| Existing Phase 10 spaCy NER (D-17) | Notice metadata extraction | ⚠ STUB — `app/ml/compliance/ner.py:49` raises NotImplementedError | — | Use `regex_patterns.py` (existing) + LLM extraction service. v2.1 swap matches D-16 BERT pattern. |
| Existing Phase 10 `regex_patterns.py` | GSTIN/PAN/CIN/section-ref extraction | ✓ at `app/ml/compliance/regex_patterns.py` | — | — |
| Existing Phase 11 APScheduler + alert pipeline | Bill reminders + connection-lost alerts | ✓ at `app/compliance/services/scheduler.py` and `app/compliance/services/alert_service.py` | — | — |
| Existing v1.0 LLM service (5-provider chain) | Bill metadata extraction | ✓ at `app/services/llm_service.py:255` (extract_with_llm) | — | — |
| Existing v1.0 storage service | Attachment upload | ✓ at `app/services/storage_service.py:137` (save_file) | — | — |
| Existing v1.0 document_tasks | Attachment classification + OCR + LLM | ✓ at `app/tasks/document_tasks.py:57` (process_document_task) | — | — |
| Phase 14 PortalFetchLog (referenced as model for GmailFetchLog) | Schema template | ✗ NOT YET BUILT (Phase 14 BLOCKED) | — | Phase 15 lands `gmail_fetch_log` standalone; Phase 14a copies the schema later. |

**Missing dependencies with no fallback:**
- `fastmcp`, `google-api-python-client`, `google-auth-oauthlib` — all required, all available on PyPI, all add to requirements.txt.

**Missing dependencies with fallback:**
- spaCy NER (D-17 reference) — fall back to regex_patterns.py + LLM extraction (covers most v2.0 needs).
- Phase 14 PortalFetchLog template — Phase 15 owns the schema design; Phase 14 reuses later.

**Unknown / pre-launch action:**
- Google Cloud OAuth verification for restricted scopes — file early; pilot can run in Testing mode for 100 users with 7-day refresh tokens.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | None (uses pyproject.toml only for build; conftest.py at `backend/tests/conftest.py`) |
| Quick run command | `cd backend && pytest tests/ -x --tb=short` |
| Full suite command | `cd backend && pytest tests/ -v` |
| RLS-aware fixtures | Existing in `backend/tests/conftest.py:91-394` (db_as_app_runtime, client_a, client_b, auditor_membership, etc.) |
| Required env vars | `DATABASE_URL` (postgres superuser for fixture creation), `FERNET_KEY` (test-mode key) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| **EMAIL-01** | OAuth round-trip — authorize URL contains correct scopes + state JWT; callback exchanges code for tokens; CSRF state validated | unit + integration | `pytest tests/test_gmail_oauth.py -x` | ❌ Wave 0 |
| **EMAIL-02** | All 6 MCP tools registered and callable in-memory; correct Pydantic schemas | unit | `pytest tests/test_gmail_mcp_tools.py -x` | ❌ Wave 0 |
| **EMAIL-03** | Refresh token round-trips through Fernet encrypt/decrypt unchanged; access tokens are NEVER persisted | unit | `pytest tests/test_gmail_credential_vault.py -x` | ❌ Wave 0 |
| **EMAIL-04** | Filter rules enforce sender_pattern + subject_pattern + label_include/exclude correctly; route_to dispatches to right handler | unit | `pytest tests/test_gmail_filter_rules.py -x` | ❌ Wave 0 |
| **EMAIL-05** | Attachment ingestion creates Document with `source_email_id` set; Celery `process_document_task` invoked unchanged | integration | `pytest tests/test_gmail_attachment_ingestion.py -x` | ❌ Wave 0 |
| **EMAIL-06** | Compliance auto-route — sender match + subject match → ComplianceNotice created at status=Received with `source=gmail`; sender match + subject mismatch → review queue row | integration | `pytest tests/test_gmail_compliance_routing.py -x` | ❌ Wave 0 |
| **EMAIL-07** | GmailFetchLog three states correctly emitted; two consecutive FETCH_FAILED triggers `gmail.connection.lost` alert | integration | `pytest tests/test_gmail_fetch_log.py -x` | ❌ Wave 0 |
| **EMAIL-08** | Dedup — second scan with same gmail_message_id is no-op; per-attachment SHA-256 within credential is UNIQUE | unit | `pytest tests/test_gmail_dedup.py -x` | ❌ Wave 0 |
| **EMAIL-09** | Audit log emitted on every MCP tool invocation with action=MCP_TOOL_CALL; PII redacted (no body, sender, or subject); body_sha256 present | unit | `pytest tests/test_gmail_audit_redaction.py -x` | ❌ Wave 0 |
| **EMAIL-10** | invalid_grant detection — RefreshError marks credential REVOKED, disables scanner job, emits `gmail.connection.lost` event | integration | `pytest tests/test_gmail_token_revocation.py -x` | ❌ Wave 0 |
| **BILL-01** | Bill auto-detect — sender heuristics + LLM correctly classify utility/telecom/credit_card/subscription emails | integration | `pytest tests/test_bill_detection.py -x` | ❌ Wave 0 |
| **BILL-02** | Bill metadata extraction — biller, amount_due, due_date, account_number_last4 correctly parsed from sample bills | unit | `pytest tests/test_bill_extractor.py -x` | ❌ Wave 0 |
| **BILL-03** | Bill dashboard — Upcoming/Due Soon/Overdue/Paid filters return correct counts; bulk-mark-paid mutates payment_status atomically | integration | `pytest tests/test_bill_dashboard.py -x` | ❌ Wave 0 |
| **BILL-04** | Pre-deadline reminders — bill_t3, bill_t1, bill_overdue alert types fire at correct times; max 3 per bill cool-down | integration | `pytest tests/test_bill_reminders.py -x` | ❌ Wave 0 |
| **BILL-05** | Mark-as-paid — payment_date/reference/method recorded; audit log row written; further reminders cancelled | integration | `pytest tests/test_bill_mark_paid.py -x` | ❌ Wave 0 |
| **BILL-06** | Recurrence — bill matching (biller_name_normalized, account_number_last4) of existing bill links via parent_bill_id; partial unique index prevents falsely matching NULL account numbers | unit | `pytest tests/test_bill_recurrence.py -x` | ❌ Wave 0 |
| **PII Lifecycle (D-34)** | Email body NEVER persisted to DB or Redis; lives only in Python local; one fetch per message | merge gate | `pytest tests/test_gmail_pii_lifecycle.py::test_body_never_persisted -x` | ❌ Wave 0 |
| **Audit immutability (D-04)** | Audit row UPDATE/DELETE raises append-only exception (Phase 9 trigger applies automatically) | merge gate | `pytest tests/test_gmail_audit_immutability.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend && pytest tests/test_gmail_*.py tests/test_bill_*.py -x --tb=short` (subset just for Phase 15 work, ~20s)
- **Per wave merge:** `cd backend && pytest tests/ -x --tb=short` (full backend suite — all 46 existing test files plus Phase 15 additions; should run < 3 min on local Postgres)
- **Phase gate:** Full suite green AND manual end-to-end smoke per the Phase 15 smoke checklist before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_gmail_oauth.py` — covers EMAIL-01 (CSRF state JWT validation, code exchange, refresh_token persistence)
- [ ] `tests/test_gmail_mcp_tools.py` — covers EMAIL-02 (6 tools registered, in-memory client invocation, Pydantic validation)
- [ ] `tests/test_gmail_credential_vault.py` — covers EMAIL-03 (Fernet round-trip; access token NEVER persisted)
- [ ] `tests/test_gmail_filter_rules.py` — covers EMAIL-04 (CRUD + match precedence)
- [ ] `tests/test_gmail_attachment_ingestion.py` — covers EMAIL-05 (Document.source_email_id FK; Celery task triggered)
- [ ] `tests/test_gmail_compliance_routing.py` — covers EMAIL-06 (binary rule confidence; review queue routing)
- [ ] `tests/test_gmail_fetch_log.py` — covers EMAIL-07 (three states, alert on 2× FAILED)
- [ ] `tests/test_gmail_dedup.py` — covers EMAIL-08 (composite UNIQUE; per-attachment SHA-256 within credential)
- [ ] `tests/test_gmail_audit_redaction.py` — covers EMAIL-09 (PII redaction in audit args; body_sha256 present; no body/sender/subject in args)
- [ ] `tests/test_gmail_token_revocation.py` — covers EMAIL-10 (RefreshError → REVOKED → scanner disabled → alert)
- [ ] `tests/test_bill_detection.py` — covers BILL-01 (sender heuristics + LLM classification correctness on synthetic bills)
- [ ] `tests/test_bill_extractor.py` — covers BILL-02 (LLM + regex fallback on bill bodies)
- [ ] `tests/test_bill_dashboard.py` — covers BILL-03 (filters + bulk-mark-paid)
- [ ] `tests/test_bill_reminders.py` — covers BILL-04 (alert scheduling + cool-down)
- [ ] `tests/test_bill_mark_paid.py` — covers BILL-05 (state transition + audit + reminder cancellation)
- [ ] `tests/test_bill_recurrence.py` — covers BILL-06 (parent_bill_id linking; partial unique index)
- [ ] `tests/test_gmail_pii_lifecycle.py` — merge gate (body never persisted; fetched once per message)
- [ ] `tests/test_gmail_audit_immutability.py` — merge gate (Phase 9 trigger blocks UPDATE/DELETE on Gmail audit rows)
- [ ] `tests/conftest.py` additions — fixtures: `gmail_credential_factory`, `mock_gmail_service` (mocks `googleapiclient.discovery.build`), `seeded_filter_rules`
- [ ] Framework install: `pip install fastmcp==3.2.4 google-api-python-client==2.196.0 google-auth-oauthlib==1.4.0` (after merge of requirements.txt)

## Sources

### Primary (HIGH confidence)

- [FastMCP — Welcome](https://gofastmcp.com/getting-started/welcome) — confirmed `@mcp.tool` decorator, stdio default
- [FastMCP — Tools (error handling)](https://gofastmcp.com/servers/tools) — confirmed `ToolError` class, `mask_error_details=True`, Pydantic model support
- [FastMCP — Running the server](https://gofastmcp.com/deployment/running-server) — confirmed transports list (stdio, http, sse, streamable-http)
- [FastMCP — Client (in-memory)](https://gofastmcp.com/clients/client) — confirmed `Client(server_instance)` in-memory transport
- [FastMCP + FastAPI integration](https://gofastmcp.com/integrations/fastapi) — confirmed `mcp.http_app()` mount + `combine_lifespans` pattern
- [FastAPI — Lifespan events](https://fastapi.tiangolo.com/advanced/events/) — confirmed `@asynccontextmanager` + `subprocess.Popen` integration
- [Gmail API — OAuth scopes](https://developers.google.com/gmail/api/auth/scopes) — confirmed `gmail.readonly` and `gmail.modify` are restricted scopes
- [Gmail API — Quota](https://developers.google.com/gmail/api/reference/quota) — confirmed quota: list=5, get=20, attachments.get=20, history.list=2 units; 1.2M/min/project; 6K/min/user; 80M/day before billing
- [Gmail API — Sync (history.list)](https://developers.google.com/gmail/api/guides/sync) — confirmed historyId pattern + 404-on-aged-out fallback
- [Gmail API — users.messages.get](https://developers.google.com/gmail/api/reference/rest/v1/users.messages/get) — confirmed format=full vs metadata vs raw
- [Gmail API — Errors handling](https://developers.google.com/gmail/api/guides/handle-errors) — confirmed exponential backoff for 429/500/503; retry from at least 1s
- [Gmail API — Message resource](https://developers.google.com/gmail/api/reference/rest/v1/users.messages) — confirmed payload/parts structure, attachment via separate endpoint
- [Google OAuth 2.0 web-server flow](https://developers.google.com/identity/protocols/oauth2/web-server) — confirmed `access_type=offline` + `prompt=consent` for refresh tokens
- [Gmail search operators](https://support.google.com/mail/answer/7190) — confirmed from:/subject:/has:attachment/label:/newer_than:/AND/OR/NOT syntax
- [google-api-python-client — Gmail messages reference](https://googleapis.github.io/google-api-python-client/docs/dyn/gmail_v1.users.messages.html) — confirmed Python signatures + response schema

### Secondary (MEDIUM confidence)

- [Nango blog — invalid_grant deep dive](https://nango.dev/blog/google-oauth-invalid-grant-token-has-been-expired-or-revoked/) — sourced 6 reasons for refresh token invalidation, including 7-day Testing-mode rule and 6-month inactivity rule
- [List of Government of India domains GitHub gist](https://gist.github.com/cyb3r-n3rd/f4e50f7c25eaa676bb99efba9c8619bf) — sourced regulatory domains list (gst.gov.in, mca.gov.in, sebi.gov.in, rbi.org.in, etc.)
- [Adding an MCP Server to your FastAPI app — Medium](https://medium.com/mindfully-ai/adding-an-mcp-server-to-your-fastapi-app-using-fastmcp-e5239afe88d6) — confirmed combine_lifespans pattern for nested lifespans
- [google-api-python-client GitHub issue #896 — 429 retry handling](https://github.com/googleapis/google-api-python-client/issues/896) — confirmed default 429 retry; batch requests need additional backoff

### Tertiary (LOW confidence — flagged for validation by planner)

- [Tech-insider FastMCP 2026 tutorial](https://tech-insider.org/mcp-server-tutorial-python-fastmcp-claude-2026/) — informational; defers to official docs
- [WebOS bank.in domain mandate by RBI](https://www.estabizz.com/rbi-bank-in-domain-guidelines-2025/) — interesting future-state but tangential; banks adopting `.bank.in` may not affect compliance email senders

### Internal sources (HIGH confidence)

- `backend/app/compliance/utils/pii_encryption.py` — Fernet helpers (Phase 9 INFRA-06)
- `backend/app/services/audit_service.py:85,137` — `log_audit_event` and `log_audit_event_strict`
- `backend/app/services/llm_service.py:15-23,255` — `CATEGORY_FIELDS["bills"]` and `extract_with_llm`
- `backend/app/services/storage_service.py:137` — `save_file()` reused
- `backend/app/tasks/document_tasks.py:57` — `process_document_task` reused
- `backend/app/compliance/services/scheduler.py:185` — APScheduler RLS pattern (CRIT-2 second pass fix)
- `backend/app/compliance/services/review_queue_service.py:72` — `enqueue_low_confidence` for low-confidence routing
- `backend/app/compliance/middleware/tenant_context.py` — RLS context middleware
- `backend/app/compliance/services/permission_registry.py` — RBAC matrix (NEW: register `email_integration:use` permission)
- `backend/app/utils/security.py:161` — `require_compliance_permission` factory
- `backend/app/services/oauth_service.py` — existing GoogleOAuth pattern (login OAuth — DO NOT reuse for Gmail)
- `backend/app/routers/auth.py:299-435` — existing OAuth signed-JWT-state CSRF pattern
- `backend/app/main.py` — currently has NO lifespan handler (Phase 15 introduces one)
- `backend/alembic/versions/0024_supabase_security_advisor_fixes.py` — current migration head; Phase 15 chains as `0025`
- `backend/app/ml/compliance/regex_patterns.py` — GSTIN/PAN/CIN/section reference extraction (reused for body extraction)
- `backend/app/ml/compliance/ner.py:49` — STUB (`NotImplementedError`); D-17 NER reuse is broken
- `backend/app/compliance/models/alert.py:37` — `VALID_ALERT_TYPES` extension point for `bill_t3`/`bill_t1`/`bill_overdue`
- `frontend/src/lib/api.ts:39` — js-cookie auth pattern (Cookies.get("token"); NOT localStorage)
- `frontend/src/app/oauth/callback/page.tsx` — login OAuth callback (separate from Gmail credential callback)
- `frontend/src/hooks/useNotificationStream.ts:43` — broken pattern (DO NOT replicate)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all PyPI versions verified 2026-05-07 against `pip index versions`
- Architecture (FastMCP transport choice): MEDIUM — strong evidence in-memory is preferable, but planner must consult product owner on whether D-31 subprocess decision is firm
- Architecture (rest): HIGH — every reused module verified by direct file inspection
- Pitfalls (1, 5, 6, 10): HIGH — code-verified
- Pitfalls (2, 3, 4, 7, 8, 9): HIGH — based on official docs + Google's published behavior
- Indian regulatory sender domains: MEDIUM — list curated from official sources but should be operator-tunable; expect community-feedback loop in early access
- Validation Architecture: HIGH — pytest 9.0.3 + existing fixture pattern is well-established

**Research date:** 2026-05-07
**Valid until:** 2026-06-06 (30 days for stable APIs); 2026-05-21 (14 days for FastMCP — version 3.2.4 is recent and the SDK is fast-moving)

**Major findings the planner MUST reconcile before plan creation:**
1. D-31 subprocess.Popen design — recommend in-memory transport instead. If D-31 is held firm, then Pattern 2 (subprocess+stdio with manual IPC) is the implementation path.
2. D-17 spaCy NER reuse — broken; use regex-only extraction in v2.0 with documented v2.1 NER swap path.
3. CONTEXT.md line 164's "httpOnly cookies" claim is inaccurate — auth uses js-cookie, not httpOnly. Frontend code should read `Cookies.get("token")` from `js-cookie`.
4. Phase 14 PortalFetchLog does not exist — Phase 15 lands `gmail_fetch_log` standalone; the schema becomes the template for future Phase 14a.
5. RBI's correct domain is `rbi.org.in` (CONTEXT.md line 67's `*.gov.in` plus authority-specific list missed this).
6. Google OAuth verification (restricted scopes) is a pre-launch dependency — file early.
