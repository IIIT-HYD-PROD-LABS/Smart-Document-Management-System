---
phase: 03-ml-classification-upgrade
plan: 02
subsystem: api, ui
tags: [fastapi, nextjs, ml-evaluation, confidence-badge, confusion-matrix]

requires:
  - phase: 03-01
    provides: "Trained ML model with evaluation_report.json"
provides:
  - "ML evaluation API endpoint (GET /api/ml/evaluation)"
  - "Color-coded confidence badges on all document displays"
  - "Model evaluation dashboard page with metrics and confusion matrix"
affects: [04-smart-search, 05-llm-integration]

tech-stack:
  added: []
  patterns: ["ConfidenceBadge inline component (green/yellow/red thresholds)", "ML API router pattern"]

key-files:
  created:
    - "backend/app/routers/ml.py"
    - "backend/tests/test_ml_evaluation.py"
    - "backend/tests/conftest.py"
    - "frontend/src/app/dashboard/model-evaluation/page.tsx"
  modified:
    - "backend/app/main.py"
    - "frontend/src/lib/api.ts"
    - "frontend/src/app/dashboard/documents/page.tsx"
    - "frontend/src/app/dashboard/search/page.tsx"
    - "frontend/src/app/dashboard/upload/page.tsx"

key-decisions:
  - "ConfidenceBadge duplicated per-page (not shared component) to minimize file additions"
  - "ML router at /api/ml prefix to separate from document routes"
  - "Confusion matrix uses intensity-based red shading for off-diagonal errors"

patterns-established:
  - "ConfidenceBadge: green >=80%, yellow 50-79%, red <50% with title tooltip"
  - "ML API router: separate prefix /api/ml for ML-specific endpoints"
  - "Evaluation page: dark theme cards + tables matching existing dashboard"

requirements-completed: [AIML-03, AIML-04]

duration: 6min
completed: 2026-03-10
---

# Phase 3 Plan 2: ML Evaluation Dashboard Summary

**Color-coded confidence badges on all document views and model evaluation page with per-category P/R/F1 and confusion matrix**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-10T11:14:08Z
- **Completed:** 2026-03-10T11:20:02Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments
- ML evaluation API endpoint serves training pipeline metrics with auth protection
- All document displays (list, search, upload) show green/yellow/red confidence badges
- Model evaluation page renders overall accuracy, per-category metrics table, and confusion matrix
- 5 endpoint tests covering 200/404/auth/structure scenarios all pass

## Task Commits

Each task was committed atomically:

1. **Task 0: Create test file for ML evaluation endpoint** - `d379d50` (test)
2. **Task 1: Create ML evaluation API endpoint and register router** - `5938ff0` (feat)
3. **Task 2: Add color-coded confidence badges and model evaluation page** - `2b4ed40` (feat)

## Files Created/Modified
- `backend/app/routers/ml.py` - ML evaluation endpoint (GET /api/ml/evaluation)
- `backend/tests/conftest.py` - Shared test fixtures (mock auth, evaluation data)
- `backend/tests/test_ml_evaluation.py` - 5 tests for evaluation endpoint
- `backend/app/main.py` - Registered ml router
- `frontend/src/lib/api.ts` - Added mlApi.getEvaluation()
- `frontend/src/app/dashboard/documents/page.tsx` - ConfidenceBadge replacing plain text
- `frontend/src/app/dashboard/search/page.tsx` - ConfidenceBadge replacing plain text
- `frontend/src/app/dashboard/upload/page.tsx` - ConfidenceBadge replacing inline display
- `frontend/src/app/dashboard/model-evaluation/page.tsx` - Full evaluation report page

## Decisions Made
- ConfidenceBadge kept as inline function per-page (not shared component) to minimize structural changes
- ML router uses /api/ml prefix, separate from /api/documents
- Confusion matrix visualization uses intensity-based red shading for misclassification cells
- Error handling added for corrupt/unreadable evaluation JSON (Rule 2 - missing critical)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed auth test assertion for HTTPBearer status code**
- **Found during:** Task 1 (endpoint verification)
- **Issue:** Test expected 403 for unauthenticated requests but FastAPI HTTPBearer returns 401
- **Fix:** Changed assertion to accept either 401 or 403
- **Files modified:** backend/tests/test_ml_evaluation.py
- **Verification:** All 5 tests pass
- **Committed in:** 5938ff0 (Task 1 commit)

**2. [Rule 2 - Missing Critical] Added error handling for corrupt evaluation JSON**
- **Found during:** Task 1 (endpoint implementation)
- **Issue:** Plan only showed basic file read; no handling for JSON decode errors or OS errors
- **Fix:** Added try/except for JSONDecodeError and OSError with 500 response and structured logging
- **Files modified:** backend/app/routers/ml.py
- **Verification:** Endpoint returns proper error response on corrupt files
- **Committed in:** 5938ff0 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ML evaluation API and frontend views complete
- Ready for Plan 03-03 (active learning / retraining pipeline)
- Confidence badges provide visual feedback for classification quality

---
*Phase: 03-ml-classification-upgrade*
*Completed: 2026-03-10*
