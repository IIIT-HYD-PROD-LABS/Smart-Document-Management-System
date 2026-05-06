---
phase: 10-ml-classification-risk-scoring
plan: 02
wave: 2
subsystem: backend
status: code-complete
completed_at: "2026-05-05"
---

# Phase 10 Plan 02 — Auto-Escalation on Critical Risk — CODE-COMPLETE

## Delivered

1. `backend/app/ml/compliance/escalation.py` — full implementation of `should_escalate`, `escalate`, `find_compliance_head_user_id`, `last_escalation_at`. Replaces the Wave 0 NotImplementedError stubs.
2. 24-hour cooldown via querying `NoticeActivity` rows tagged `details.source='critical_escalation'` — defense against escalation storms when a score oscillates near the 85 threshold.
3. `compliance_tasks.classify_and_score_notice` — Step 7 (escalation hook) replaces the Phase 9 TODO comments; calls `should_escalate` then `escalate` only when tier == 'critical'. Failure is non-fatal (logged) — risk score persistence is not rolled back if escalation fails.
4. NoticeActivity row written on escalation: `type='assigned'`, `details.source='critical_escalation'`, with full SHAP factor copy + before/after assigned_user_id.
5. Immutable AuditLog row written: `action='notice_escalated'` with risk_score, risk_tier, model_version, before/after value diff. Survives via Phase 9 INFRA-07 trigger + REVOKE on app_runtime.
6. Special case handled: client has no compliance_head — logs warning, writes activity + audit row with `assigned_user_id=NULL` so the dashboard surfaces "Critical: needs assignment".
7. Tests: `tests/test_escalation.py` (9 unit tests covering tier gating, cooldown enforcement, exact boundary, missing compliance_head, last_escalation_at filter by source). Plus 1 integration test in `test_classify_and_score_task.py` verifying the wired-up Celery task triggers `escalate` on Critical tier.

## Acceptance verification

- 9 escalation unit tests GREEN
- `test_critical_tier_triggers_escalation` GREEN (Celery wiring)
- 41 backend regression tests GREEN
- Cooldown logic uses `>=` so the boundary triggers re-escalation at exactly 24h — verified by `test_should_escalate_true_at_exact_cooldown_boundary`

## Notes

- Cross-channel alert delivery (email/SMS/WebSocket) is **Phase 11**'s job; Plan 02 only emits the activity row + audit log that Phase 11 will subscribe to.
- The default escalation chain is single-hop (`compliance_head` only) for v2.0; per-client multi-hop chain (CFO → external counsel) is wired in Phase 11 via `config_overrides` JSONB.
- Escalation transaction boundary: failure to write activity/audit does NOT roll back the risk score that was already persisted. The risk score is the system-of-record fact; escalation is a derived action that the daily `recompute_all_risk_scores` cron retries with cooldown enforced.
