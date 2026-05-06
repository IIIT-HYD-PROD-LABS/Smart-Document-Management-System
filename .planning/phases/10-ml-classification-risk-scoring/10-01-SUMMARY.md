---
phase: 10-ml-classification-risk-scoring
plan: 01
wave: 1
subsystem: backend
status: code-complete
completed_at: "2026-05-05"
---

# Phase 10 Plan 01 — Review Queue Backend — CODE-COMPLETE

## Delivered

1. `backend/app/compliance/models/review_queue.py` — `NoticeReviewQueue` ORM mapping migration 0020's table.
2. `backend/app/compliance/schemas/review_queue.py` — `ReviewQueueOut`, `ReviewQueueAssignRequest`, `ReviewQueueAssignResponse`, `ReviewQueueListResponse`.
3. `backend/app/compliance/services/review_queue_service.py` — `enqueue_low_confidence` (idempotent ON CONFLICT upsert), `list_pending` (RLS-scoped), `assign_reviewer_label` (mutates parent notice + writes activity + audit).
4. `backend/app/compliance/routers/review_queue.py` — `GET /api/compliance/review/pending`, `GET /api/compliance/review/{id}`, `PATCH /api/compliance/review/{id}/assign`. Mounted in `app/main.py`.
5. `backend/app/compliance/services/permission_registry.py` — `NOTICE_REVIEW` permission added; granted to `compliance_head`, `ca_consultant`, `legal_team`.
6. `backend/app/tasks/compliance_tasks.py` — wired `enqueue_low_confidence` hook after risk scoring (no-op for v2.0 since BERT confidences stay NULL; activates automatically when v2.1 BERT ships).
7. Tests: `tests/test_review_queue_service.py` (9 unit tests, MagicMock-based), extended `tests/test_permission_registry.py` (7 NOTICE_REVIEW grant tests), extended `tests/test_compliance_endpoints.py::ROLE_PERMISSION_MATRIX` (84 → 91 cases, 7×13).

## Acceptance verification

- 29 tests GREEN: `pytest tests/test_review_queue_service.py tests/test_permission_registry.py`
- 41 tests GREEN: `pytest tests/test_classify_and_score_task.py tests/test_risk_scorer.py tests/test_compliance_regex_patterns.py` (no regressions)
- OpenAPI surface verified: `/api/compliance/review/{pending,id,id/assign}` exposed
- Migration head: `0020_phase10_ml_columns_and_review_queue` (already applied)
- 82 tests total GREEN across Plan 10-01 + 10-02 + 10-03 + supporting suites

## Notes

- The hook in `compliance_tasks.py` only fires `enqueue_low_confidence` when at least one classifier confidence is non-NULL. v2.0 default state (rule-based scorer; BERT confidences NULL) is documented as no-op — the test `test_no_review_queue_enqueue_when_classifier_confidences_null` enforces this.
- `assign_reviewer_label` uses NoticeActivity `type='assigned'` rather than introducing a new event type — avoids a CHECK-constraint migration; semantically a reviewer override IS an authoritative re-assignment.
- The `ON CONFLICT (notice_id) DO UPDATE` reset of `reviewed_at` to NULL is intentional: a re-classification with new confidence values re-opens review, even if previously closed. This is the v2.1 retraining contract.
