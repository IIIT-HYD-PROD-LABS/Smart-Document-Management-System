---
phase: 13-elasticsearch-search-reporting
status: planned
created_at: "2026-05-05"
ship_target: v2.0
---

# Phase 13 v2.0 Execution Plan

Single-wave plan derived from `13-RESEARCH-FINAL.md`. Ships unified search
+ reports on PostgreSQL FTS; defers Elastic Cloud integration to v2.1.

## Build order

### Wave 1 — Data layer
- `backend/alembic/versions/0023_phase13_search_vector_on_notices.py`
  - ADD COLUMN `compliance_notices.search_vector` TSVECTOR
  - CREATE INDEX `ix_compliance_notices_search_vector` USING GIN
  - CREATE FUNCTION + TRIGGER to maintain the vector on INSERT/UPDATE
  - Backfill existing rows
- ORM: add `search_vector = Column(TSVECTOR, nullable=True)` to
  `app/compliance/models/notice.py`

### Wave 2 — Service layer
- `app/compliance/services/unified_search_service.py`:
  - `search(query, entity_types=("notice","document"), client_id, page, page_size)`
  - SQL: `SELECT ... ts_rank ... UNION ALL ... ORDER BY rank DESC LIMIT ...`
  - Returns `[{entity_type, id, rank, snippet, ...minimal fields...}]`
- `app/compliance/services/report_service.py` extensions:
  - `penalty_by_authority(client_id, window_days)`
  - `notice_volume_by_status(client_id, window_days)`
  - `response_time_distribution(client_id, window_days)`
- All RLS-scoped via existing tenant_context middleware

### Wave 3 — Router layer
- `app/compliance/routers/search.py` — new router, mount at
  `/api/compliance/search/*`
- `GET /unified?q=...&entity_types=...&page=...&page_size=...`
- Extend existing `app/compliance/routers/reports.py` with 3 new GET
  endpoints (NOT new router — keeps the surface coherent)

### Wave 4 — Frontend
- `frontend/src/types/compliance.ts` — `UnifiedSearchHit`,
  `PenaltyByAuthority`, `NoticeVolumeByStatus`, `ResponseTimeDistribution`
- `frontend/src/lib/api/compliance.ts` — API client extensions
- `frontend/src/app/dashboard/compliance/search/page.tsx` — new page
- `frontend/src/app/dashboard/compliance/reports/page.tsx` — extend
  with new analytics tabs (existing health-summary tab retained)
- Sidebar nav entry for "Search"

### Wave 5 — Tests
- `tests/test_unified_search_service.py` — query construction tests
- `tests/test_report_service_aggregations.py` — aggregation correctness
- `tests/test_search_router.py` — endpoint smoke
- Migration smoke: insert → search → result returned

### Wave 6 — Docs
- 13-EXECUTION-SUMMARY.md
- STATE.md / ROADMAP.md / README.md updates

## Acceptance gates

1. Migration 0023 applied; `compliance_notices.search_vector` populated
   on existing rows
2. `/api/compliance/search/unified?q=foo` returns 200 with merged
   notice + document hits, ranked
3. Reports endpoints return aggregations in <500ms at v2.0 launch
   volume (<10K notices)
4. ≥150 backend tests GREEN (147 pre-Phase-13 + new tests)
5. Frontend search page + extended reports page render and route
   correctly

## Risks

- **Risk:** Trigger function on `compliance_notices` may slow bulk inserts
  measurably. **Mitigation:** PG triggers run per-row at INSERT time;
  benchmark via existing seed scripts. If material, switch to deferrable
  constraint trigger or async background recompute (defer to v2.1).
- **Risk:** UNION ALL query plan may not use both indexes optimally for
  large result sets. **Mitigation:** EXPLAIN ANALYZE during development;
  cap page_size at 50 to keep it bounded.
