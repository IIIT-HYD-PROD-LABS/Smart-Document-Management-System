# Phase 15: Gmail MCP Integration & Email Document Ingestion - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `15-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 15-gmail-mcp-integration
**Areas discussed:** MCP server library, Bill data model, Email body PII lifecycle, Compliance auto-routing without BERT
**Pre-existing seed:** 28 decisions from 2026-04-28 (carried forward, mostly unchanged)
**Refinement outcome:** 9 new decisions (D-29 through D-37) + 5 revisions (D-16, D-19, D-22, D-25, D-27, D-28)

---

## Area selection

| Area | Description | Selected |
|---|---|---|
| MCP server library | Python `mcp` SDK vs FastMCP vs custom; transport mix; lifecycle | ✓ |
| Bill data model | Separate table vs extend Document; URL shape; recurrence signal | ✓ |
| Email body PII lifecycle | Fetch pattern; audit granularity; redaction policy | ✓ |
| Compliance auto-routing without BERT | v2.0 fallback strategy given Phase 10 BERT deferral | ✓ |

**User selected:** All four (multi-select).

---

## Area A: MCP server library

### A.1 Which MCP server library?

| Option | Description | Selected |
|---|---|---|
| FastMCP | Decorator-based tool registration over the official `mcp` SDK; ~5x less boilerplate per tool; spec-compliant via wrapper | ✓ |
| Official `mcp` Python SDK | Reference implementation; verbose tool registration; closest to spec docs | |
| Custom stdio loop | Hand-rolled JSON-RPC framing; zero deps; full control | |

**User's choice:** FastMCP (Recommended)
**Notes:** No deviation; locked as recommended.

### A.2 Transport surface in v2.0?

| Option | Description | Selected |
|---|---|---|
| stdio only | All v2.0 consumers are internal Phase 12 agents in same container; no network listener | ✓ |
| stdio + HTTP/SSE both | Future-proofs for in-cluster agents; doubles testing surface | |
| HTTP/SSE only | Cleaner for non-Python consumers; loses subprocess simplicity | |

**User's choice:** stdio only (Recommended)
**Notes:** Locks D-27's "internal-only" guard structurally — no listener exists.

### A.3 MCP server lifecycle?

| Option | Description | Selected |
|---|---|---|
| Backend entrypoint spawns child via subprocess.Popen | FastAPI startup hook; dies with parent; shares env | ✓ |
| Separate compose service | Cleaner process boundary; duplicates env config + container overhead | |
| Lazy-start on first MCP request | Saves resources if MCP unused; adds first-call latency | |

**User's choice:** Backend entrypoint spawns child (Recommended)

---

## Area B: Bill data model

### B.1 Bill data model — separate entity or extend Document?

| Option | Description | Selected |
|---|---|---|
| Separate `bills` table | New ORM with payment-cycle semantics; matches seed D-19 | |
| Extend `documents` with `category='bill'` + columns | Reuse table; risks kitchen-sink schema | |
| Hybrid — bills metadata in new table; documents stores PDF | 1:0..1 FK from bill.source_document_id → documents.id; clean separation | ✓ |

**User's choice:** "do which is best" (free text — deferral to recommendation)
**Reflected back as:** Hybrid (option 3) — most precise about the FK relationship; cleanly handles bills without attachments
**Notes:** The hybrid is the seed's D-19 with the FK named explicitly. Bills WITHOUT attachments have `source_document_id=NULL`.

### B.2 Bill detail page URL?

| Option | Description | Selected |
|---|---|---|
| /dashboard/email/bills/[id] | Dedicated route; deep-linkable; matches D-24 route family | ✓ |
| Inline drawer on /email/bills | No separate route; faster nav; loses deep-link | |
| Reuse /dashboard/documents/[id] when source_document_id exists | Single page handles both perspectives; no-attachment bills still need own page | |

**User's choice:** /dashboard/email/bills/[id] (Recommended)

### B.3 Recurring-bill clustering signal?

| Option | Description | Selected |
|---|---|---|
| (biller_name, account_number_last4) | Robust against name variation; rare false positives | ✓ |
| (biller_name, amount_due ±10%) | Catches subscriptions without last-4; brittle for variable utility bills | |
| User-confirmed clustering only | Highest accuracy; slowest UX | |

**User's choice:** (biller_name, account_number_last4) (Recommended per seed D-23)
**Notes:** Biller name normalized via regex (case + whitespace + suffix stripping like LTD/LIMITED/PVT).

---

## Area C: Email body PII lifecycle

### C.1 How should the email body be fetched + cached during ingestion?

| Option | Description | Selected |
|---|---|---|
| Fetch-once, classify+extract, discard | Body in Python locals for ~seconds; single PII touchpoint per message | ✓ |
| Fetch on every demand (no cache) | Strongest privacy; multiplies Gmail quota + audit volume | |
| Fetch + cache in Redis with TTL | Fast subsequent reads; PII at rest in Redis even briefly | |

**User's choice:** Fetch-once, classify+extract, discard (Recommended)

### C.2 Audit log granularity for email bodies?

| Option | Description | Selected |
|---|---|---|
| One row per MCP_TOOL_CALL with body SHA-256 | Provable tampering detection without storing body | ✓ |
| Row per operation that touched body | Maximum traceability; higher audit volume | |
| Just the MCP call, no body hash | Faster, leaner; loses fetch-time proof | |

**User's choice:** One row per MCP_TOOL_CALL with body SHA-256 (Recommended)

### C.3 PII redaction in audit args?

| Option | Description | Selected |
|---|---|---|
| Redact bodies + attachments + subjects + senders; keep IDs + SHA-256 | No raw email content anywhere in audit; cleanest privacy posture | ✓ |
| Redact bodies only; keep subject + sender | Useful for incident triage; subjects can leak PII | |
| Custom redaction rules per filter route | Per-rule audit policy; more complex | |

**User's choice:** Redact bodies + attachments; keep IDs + SHA-256 (Recommended)
**Notes:** Trade-off accepted — marginally harder incident triage in exchange for tribunal-grade privacy.

---

## Area D: Compliance auto-routing without BERT

### D.1 v2.0 fallback for compliance auto-routing?

| Option | Description | Selected |
|---|---|---|
| Rule-based detector + Phase 10 rule-scorer | Sender-domain regex + subject keyword match; binary confidence; v2.1 swaps in BERT | ✓ |
| Everything to Review queue, no auto-create | Safest; zero auto-classification risk; 0% magical until BERT | |
| Defer notice routing to v2.1; ship bills + dms_only this milestone | Smallest ship; cleanest demo; loses headline feature | |

**User's choice:** Rule-based detector + Phase 10 rule-scorer (Recommended)
**Notes:** v2.1 BERT swap-in is a one-file replacement (`gmail_classifier.py`) — schema, audit, status workflow all unchanged.

### D.2 Auto-created notice status?

| Option | Description | Selected |
|---|---|---|
| Received + 'auto-imported' badge on detail page | Standard Phase 9 Received status; UI badge for visual distinction | ✓ |
| New status: Auto-Received (pre-Received) | Adds 6th workflow status; requires enum migration | |
| Received with quiet flag, no UI badge | Cleanest UX; loses at-a-glance distinction | |

**User's choice:** Received + 'auto-imported' badge (Recommended)
**Notes:** Avoids Phase 9 enum migration; indistinguishable from manual upload at API/audit/transition level.

### D.3 Forwarded-notice handling?

| Option | Description | Selected |
|---|---|---|
| Route to dms_only — saved as document, no auto-routing | Avoids false-positive ComplianceNotice; v2.1 BERT handles content-based detection | ✓ |
| Route to Review queue with 'forwarded notice' flag | First-class forwarder workflow now; more UI work | |
| Ignore (skip ingestion) | Cleanest; loses document silently | |

**User's choice:** Route to dms_only (Recommended)

---

## Final wrap-up

**Question:** Anything else to discuss before writing CONTEXT.md?

| Option | Description | Selected |
|---|---|---|
| I'm ready for context | Write 15-CONTEXT.md with the 28 seed + 12 new = 40 locked decisions | ✓ |
| Explore more gray areas | Surface more open questions (cadence, transport future-proofing, reminder semantics, label UX) | |

**User's choice:** I'm ready for context

---

## Claude's Discretion (areas not asked)

User did not explicitly defer to Claude on individual questions, but the seed CONTEXT.md and refined CONTEXT.md include a "Claude's Discretion" subsection covering: scanner cadence default tuning, Pydantic schema specifics, MCP error envelope format, bill `payment_method` enum, bill detail page layout, Gmail label-management UX in v2.0, LLM prompt versioning, and migration ordering relative to Phase 14.

## Deferred Ideas

No new deferred ideas surfaced during the 4-area discussion that weren't already in the seed's deferred list. New deferred items added to CONTEXT.md based on the discussion:
- MCP HTTP/SSE transport (deferred to v2.1 per D-30)
- BERT-based compliance classifier (deferred to v2.1 per D-16 revision)
- Forwarded-notice content classification (deferred to v2.1 per D-33)
- Auto-Received pre-acknowledgement status (rejected in favor of UI badge per D-32)
