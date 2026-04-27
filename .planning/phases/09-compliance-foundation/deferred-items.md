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

## Plan 09-06 — pre-existing v1.0 lint errors in `frontend/src/app/dashboard/upload/page.tsx`

Discovered while running `npm run lint` during Plan 09-06 execution. 5 errors:

- 37:24 Error — React Hook `useCallback` called conditionally
- 41:34 Error — React Hook `useCallback` called conditionally
- 66:5  Error — React Hook `useEffect` called conditionally
- 73:20 Error — React Hook `useCallback` called conditionally
- 77:59 Error — React Hook `useDropzone` called conditionally

Root cause: hooks declared inside an early-return guard (`if (!user) { return; }`)
violates Rules of Hooks. Pre-existing v1.0 code; Phase 09 did not touch this file.
Fix is mechanical (move early-return after all hooks) but unrelated to compliance
work. Track in v1.0 backlog.

Plus 2 warnings (also v1.0):
- `dashboard/documents/[id]/page.tsx` 300:8 — useCallback unnecessary dep
- `dashboard/documents/[id]/preview/page.tsx` 248:25 — `<img>` instead of `<Image />`
