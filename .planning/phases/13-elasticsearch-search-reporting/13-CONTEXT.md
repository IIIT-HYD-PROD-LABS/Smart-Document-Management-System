# Phase 13: Elasticsearch + Cross-Entity Search + Reporting - Context

**Gathered:** 2026-05-05 (seed scope; awaiting `/gsd:discuss-phase 13`)
**Status:** CONTEXT seeded

<domain>
## Phase Boundary

**In scope:** A single search query returns ranked results spanning compliance
notices AND DMS documents. Aggregation-driven reports (penalty analytics,
response time, compliance health) render with sub-3-second loads via
Elasticsearch aggregations. Automatic fallback to PostgreSQL FTS when ES
is unavailable — users see a degraded-mode banner but no functionality
loss.

**Specifically:**
1. Elasticsearch managed service (Elastic Cloud) — index `notices` +
   reuse v1.0 `documents` index from Phase 4
2. Cross-system unified search endpoint at `/api/search/unified` — merges
   notice + document hits with deterministic ordering by ts_rank
3. Transactional outbox pattern — every notice + document mutation writes
   an `outbox_event` row; a dedicated indexer worker drains the outbox
   and pushes to ES, providing eventual-consistency guarantees
4. Daily reconciliation job — diff between PostgreSQL row count and ES
   doc count; auto-repair on drift > 1%
5. Compliance reports surfacing aggregations: by-authority, by-type,
   penalty-by-month, response-time-by-tier
6. Compliance health score dashboard — rolling 90/180/365-day scores +
   trend chart
7. PostgreSQL fallback path — when ES is unreachable, search hits
   `compliance_notices` + `documents` FTS columns; degraded indicator
   surfaces on UI

**Out of scope:**
- Real-time search-as-you-type below 200ms — defer; v2.0 ships sub-3s
- Vector / semantic search — v3.0 once labeled corpus exists
- Multi-language search — English-only in v2.0
- Cross-tenant search (compliance head sees notices across multiple
  clients in cross-client mode) — v2.0 ships this; per-user customization deferred

</domain>

<decisions>
## Proposed Decisions (refine via `/gsd:discuss-phase 13`)

### ES infrastructure (INFRA-02)
- **D-01:** Elastic Cloud Standard tier — 2 GB heap × 2 nodes
  (~$80/mo). Self-hosting on Render exhausted memory in benchmarks; managed
  is the lower-risk path.
- **D-02:** Index strategy — separate `notices` and `documents` indices
  (different mappings, different lifecycle); search across both via
  multi-index queries. Avoids forcing schema convergence.
- **D-03:** Mapping for `notices`: text fields with `english` analyzer,
  keyword aliases for facet filters (authority, status, risk_tier, GSTIN/PAN).
- **D-04:** Pinned ES Python client version 8.x to match server version.

### Outbox pattern (INFRA-02)
- **D-05:** New `outbox_events` table (event_type, aggregate_type,
  aggregate_id, payload JSONB, created_at, processed_at). Migration adds
  trigger functions on `compliance_notices` + `documents` to write outbox
  rows on INSERT / UPDATE.
- **D-06:** Dedicated `indexer-worker` Celery service draining outbox in
  FIFO order. Bulk-flushes to ES every 1s OR 100 events, whichever first.
  At-least-once delivery; ES re-index is idempotent.

### Reconciliation (drift detection)
- **D-07:** Nightly cron at 03:00 IST — query both PG and ES for hash of
  (id, updated_at) per index. Drift > 1% triggers full re-index of the
  affected aggregate ID range; admin alert via Phase 11 pipeline.

### Reports (AUDIT-03..07)
- **D-08:** Aggregation queries hit ES (sub-second). Materialized PostgreSQL
  views are the v2.0 fallback path so the dashboard works without ES.
- **D-09:** Penalty analytics — sum + bucket by month + by authority.
  Reports endpoint returns data shape compatible with Recharts (frontend stack from Phase 7).
- **D-10:** Compliance health score — extends Phase 11 D-14 with severity
  weighting (CA/CFO sign-off required first).

### Frontend (UI hint: yes)
- **D-11:** `/dashboard/compliance/search` unified search bar +
  filter sidebar (Phase 9 NoticeFilterSidebar pattern reused).
- **D-12:** `/dashboard/compliance/reports` — extends Phase 9 reports page
  with new tabs (penalty analytics, response time, health score trend).
- **D-13:** ES degraded-mode banner — `<aria-live="polite">`-region in the
  dashboard layout when fallback is active.

</decisions>

<canonical_refs>
- `backend/app/services/search.py` — v1.0 PostgreSQL FTS fallback (Phase 4)
- `backend/app/models/document.py` — Document model with FTS column
- `backend/app/compliance/models/notice.py` — ComplianceNotice (FTS to be added in this phase)
- `frontend/src/components/compliance/NoticeFilterSidebar.tsx` — facet pattern
- `.planning/REQUIREMENTS.md` — INFRA-02, EVID-05, AUDIT-03..07
</canonical_refs>

<deferred>
- Real-time search-as-you-type — v2.1
- Vector / semantic search via embeddings — v3.0
- Multi-language indices (Hindi) — v3.0
- Cross-region failover for ES — v3.0
</deferred>

## Open Blockers (resolve during `/gsd:research-phase 13`)
1. **Elastic Cloud subscription approval** — cost approval needed (~$80/mo
   recurring). v2.0 RESEARCH-FINAL must commit either Elastic Cloud or
   self-hosted-with-OOM-guards.
2. **Index lifecycle policy** — retain how long? GDPR deletion requests
   need to propagate to ES too.
3. **Bulk re-index downtime** — full corpus re-index (~50K docs at v2.0
   launch) takes ~10 min; do we ship an "indexing in progress" banner or
   gate the search page entirely?
4. **Compliance health score severity weights** — depends on Phase 10
   D-13 placeholder values being ratified.
