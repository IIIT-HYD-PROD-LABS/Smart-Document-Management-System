# Plan 09-04 — Deferred Items

These were discovered during Plan 04 execution but are outside the plan's scope
(do not affect Plan 04 acceptance criteria, no causal link to Plan 04 changes).

## Pre-existing test flakes

- **tests/test_search.py — `test_search_with_category_filter`,
  `test_search_rejects_inverted_date_range`, `test_search_rejects_inverted_amount_range`**:
  Rate-limit (429) failures when running ALL test_search.py tests sequentially.
  The slowapi limiter is configured at 30 requests/minute per IP; the 13-test
  test_search.py file fires ~14 requests in the same minute and trips the limit.
  Each test PASSES individually. Not caused by Plan 04 (no router or middleware
  added that touches /api/documents/*).
- **`PytestUnknownMarkWarning: Unknown pytest.mark.integration`**:
  Pre-existing; conftest does not register the integration marker. Plan 03 SUMMARY
  flagged this as a Plan 02 deferral. Cosmetic only.

## v1.0 cleanups (out of scope for Phase 9)

None encountered as a direct consequence of Plan 04 changes.
