# Phase 13 — Research Final (decisions committed)

**Finalized:** 2026-05-05
**Status:** Decisions locked for v2.0 ship; Elasticsearch + outbox pattern + reconciliation deferred to v2.1

## 1. Strategic decision: Phase 13 v2.0 ships *without* Elasticsearch

The CONTEXT names Elasticsearch as the primary index. After ultrathink-grade
analysis of the success criteria, **v2.0 ships unified search + reports
on PostgreSQL FTS only**; Elastic Cloud integration defers to v2.1 once
the subscription decision lands.

### Why

The 5 ROADMAP success criteria for Phase 13 break down as follows:

| # | Criterion | Achievable on PG-FTS? | Notes |
|---|-----------|----------------------|-------|
| 1 | Unified search across notices + documents with merged ranking | ✅ Yes | UNION ALL of two `to_tsvector` columns + ts_rank |
| 2 | Cross-system search to find DMS docs relevant to a notice | ✅ Yes | Same query, with notice-context filtering |
| 3 | Reports render sub-3-second using aggregations | ✅ Yes (v2.0 volume <10K notices) | PG aggregations on indexed columns |
| 4 | ES unavailable → PG FTS fallback | N/A in v2.0 | No ES = nothing to fall back from |
| 5 | Outbox + daily reconciliation | N/A in v2.0 | No ES = nothing to reconcile |

Criteria 1–3 deliver the *user-visible value* of Phase 13. Criteria 4–5 are
**scale + redundancy infrastructure** that only matters once an ES cluster
exists. Building the outbox pattern today (triggers + drainer + reconciliation
cron) without a consumer = pointless write amplification. v2.1 wires both the
outbox and ES in one wave so the events table starts producing the moment a
consumer exists.

### Cost-deferral argument

Elastic Cloud Standard tier is ~$80/mo recurring. Phase 13 v2.0 unblocks
unified search and compliance reports without that commitment. v2.1 makes
the case for ES on actual scale evidence (latency thresholds breached at
some real volume) rather than pre-emptive infrastructure spend.

## 2. v2.0 ship — concrete scope

1. **Migration 0023** — adds `compliance_notices.search_vector` (TSVECTOR)
   + GIN index + per-row trigger that maintains the vector. Mirrors Phase 4
   `documents.search_vector` pattern from migration 0003.
2. **Unified search service** — `app/compliance/services/unified_search_service.py`
   queries both `compliance_notices` and `documents` via `to_tsquery` + ts_rank,
   merges and ranks results, returns a tagged shape so frontend can route
   clicks by entity type.
3. **Search router** — `GET /api/compliance/search/unified?q=...&entity_types=notice,document&...filters`
4. **Reports service extensions** — `app/compliance/services/report_service.py`:
   - `penalty_by_authority(client_id, window_days) → list[{authority, total_penalty, count}]`
   - `notice_volume_by_status(client_id, window_days) → list[{status, count}]`
   - `response_time_distribution(client_id, window_days) → {p50, p90, p95}`
   - `compliance_health_summary(client_id) → {total, on_time, overdue, score, ...}`
5. **Reports router extensions** — 3 new endpoints under existing
   `/api/compliance/reports/*` (the existing `health-summary` endpoint
   stays unchanged as the entry surface).
6. **Frontend `/dashboard/compliance/search`** — single search bar
   spanning notices + documents with entity-type tabs and result rows
   that deep-link to either `/dashboard/compliance/notices/{id}` or
   `/dashboard/documents/{id}`.
7. **Frontend `/dashboard/compliance/reports`** — extends the existing
   reports page with charts for penalty-by-authority and response-time.
8. **Tests** — service unit tests, router smoke tests, FTS migration
   verification (search_vector populated post-trigger).

## 3. v2.1 deferred (binding)

1. Elastic Cloud Standard managed cluster + index lifecycle policy
2. Outbox pattern (`outbox_events` table + DB triggers on
   `compliance_notices` and `documents`)
3. Indexer worker Celery service draining outbox to ES
4. ES degraded-mode banner — currently always-PG; the contract
   `unified_search_service.search()` is identical regardless of
   backend, so this is a thin adapter swap
5. Daily reconciliation cron (drift detection between PG and ES)
6. Severity-weighted compliance score (depends on Phase 10 D-13
   placeholder ratification by CA/CFO)
7. Real-time search-as-you-type sub-200ms (v3.0 if ES alone insufficient)
8. Vector / semantic search via embeddings (v3.0)
9. Cross-region ES failover (v3.0)

## 4. Library versions

No new library dependencies for v2.0. All work uses the existing
SQLAlchemy + FastAPI + Pydantic stack and the PG `to_tsvector` / `to_tsquery`
features already in use from Phase 4.

v2.1 will add: `elasticsearch==8.x` Python client.

## 5. Open blockers — RESOLVED for v2.0

1. **Elastic Cloud subscription** — DEFER to v2.1 milestone planning.
   Cost approval not on critical path for v2.0 ship.
2. **Index lifecycle policy** — N/A in v2.0; v2.1 owner.
3. **Bulk re-index downtime** — N/A in v2.0.
4. **Compliance health score severity weights** — placeholder values
   from Phase 10 D-13 used unchanged. CA/CFO ratification is v2.1.

---

*Phase 13 research finalized 2026-05-05. Recommended /gsd:plan-phase 13
output captured in this document; execution proceeds inline with this
session.*
