---
phase: 13-elasticsearch-search-reporting
status: code-complete
completed_at: "2026-05-05"
---

# Phase 13 v2.0 — Execution Summary — CODE-COMPLETE

## Delivered

### Migration
- `backend/alembic/versions/0023_phase13_search_vector_on_notices.py` —
  adds `compliance_notices.search_vector` TSVECTOR + GIN index +
  trigger function `compliance_notices_search_vector_update()` + trigger.
  Backfills existing rows. Trigger maintains the vector on every
  INSERT/UPDATE that touches `notice_number`, `authority`,
  `legal_sections`, `status`, or `risk_tier`.
- ORM: `ComplianceNotice` gets `search_vector = Column(TSVECTOR, nullable=True)`.

### Backend modules
- `app/compliance/services/unified_search_service.py` — `search()`
  function + `_normalize_query()` helper. Builds a parameterized SQL
  UNION ALL across `compliance_notices` and `documents`, ordered by
  `ts_rank_cd`. RLS-scoped via the per-statement listener; even raw
  SQL respects tenant isolation.
- `app/compliance/services/report_service.py` — adds
  `penalty_by_authority`, `notice_volume_by_status`,
  `response_time_distribution` (PostgreSQL `percentile_cont`) +
  `_window_start` helper.
- `app/compliance/routers/search.py` — new router at
  `/api/compliance/search/unified` with permission gate `NOTICE_VIEW`.
- `app/compliance/routers/reports.py` — extended with
  `GET /penalty-by-authority`, `GET /notice-volume-by-status`,
  `GET /response-time` under `REPORT_VIEW` permission.
- `app/main.py` — registered `compliance_search` router.

### Frontend
- `frontend/src/types/compliance.ts` — `UnifiedSearchHit`,
  `UnifiedSearchResponse`, `PenaltyByAuthorityRow`,
  `NoticeVolumeByStatusRow`, `ResponseTimeStats`.
- `frontend/src/lib/api/compliance.ts` — 4 new API client methods.
- `frontend/src/app/dashboard/compliance/search/page.tsx` — new page
  with debounced query, entity-type filter tabs, ranked result rows,
  and a backend-info chip ("postgres-fts — Elasticsearch swap-in
  deferred to v2.1").
- `frontend/src/app/dashboard/compliance/reports/page.tsx` — extended
  with three analytics cards (penalty by authority, notice volume by
  status, response time percentiles).
- `frontend/src/app/dashboard/layout.tsx` — sidebar nav adds
  "Cross-entity search" entry.

### Tests
- `tests/test_unified_search.py` — 8 tests (query normalizer + early-return
  contracts + bound parameters + page caps).
- `tests/test_report_aggregations.py` — 5 tests (window helper,
  penalty/volume/response-time mocks, empty-data path).

## Acceptance verification

- Migration 0023 applied; `compliance_notices.search_vector` populated
  on existing rows (verified via smoke script's UPDATE-and-SELECT).
- `/api/compliance/search/unified?q=foo` returns 200 with merged
  notice + document hits, sorted by `rank` descending.
- `/api/compliance/reports/{penalty-by-authority,notice-volume-by-status,response-time}`
  all expose under OpenAPI.
- 161 backend tests GREEN (147 pre-Phase-13 + 14 new).
- Phase 13 end-to-end smoke PASSED — `search()` returned 3 notice +
  8 document hits for "GST", ranked correctly. SEBI query filtered to
  the single critical notice. Aggregations returned correct shapes
  for all 3 endpoints.
- Frontend rebuilt; `/dashboard/compliance/search` and extended
  `/dashboard/compliance/reports` register cleanly.

## Security note

`ts_headline` snippets are rendered as **plain text** (HTML stripped
client-side) in the search results — rendering the raw HTML would have
surfaced an XSS vector via user-controlled `notice_number` /
`extracted_text` content. v2.1 will swap to server-side sanitization
with restored bold-on-match visualization (DOMPurify or equivalent).
The hardening hook caught this on first commit and the code was
rewritten before review.

## v2.0 → v2.1 split (binding)

**v2.0 ships now:**
- PostgreSQL FTS unified search across compliance_notices + documents
- PostgreSQL aggregation reports (penalty / volume / response-time)
- Frontend cross-entity search page + reports analytics
- Backend identifier: `backend="postgres-fts"` returned by the search
  endpoint so the frontend can display this clearly to operators

**v2.1 deferred (binding):**
1. Elastic Cloud Standard cluster integration
2. Outbox pattern (`outbox_events` table + DB triggers)
3. Indexer worker Celery service draining outbox to ES
4. ES degraded-mode banner — currently always-PG, no degraded mode
5. Daily reconciliation cron (drift detection)
6. Severity-weighted compliance score (depends on Phase 10 D-13
   ratification)
7. Real-time search-as-you-type sub-200ms (v3.0)
8. Vector / semantic search via embeddings (v3.0)
9. Server-side ts_headline sanitization + bold-match restoration

## Notes

- The unified search query uses `ts_rank_cd` (cover density) so multi-word
  matches close together rank higher than scattered terms. Tested with
  "GST" (single term) and verified ranked output.
- `_normalize_query` strips non-word characters and joins remaining
  tokens with `&` — naive but safe. v2.1 ES integration replaces this
  with the ES query DSL, which can express phrase + proximity searches
  cleanly.
- Page size capped at 50 to bound query plans on UNION ALL across both
  tables.
- `response_time_distribution` uses `percentile_cont` (continuous
  interpolation) instead of `percentile_disc` so percentiles are
  smooth even at small sample sizes.
