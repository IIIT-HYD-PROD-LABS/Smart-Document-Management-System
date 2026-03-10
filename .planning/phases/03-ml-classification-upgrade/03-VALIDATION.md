---
phase: 3
slug: ml-classification-upgrade
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.4.3 |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds (unit), ~5min (full training) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green + training accuracy >85%
- **Max feedback latency:** 30 seconds (unit tests)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | AIML-01, AIML-02 | integration | `python -m app.ml.train --real-only` | existing | pending |
| 03-01-02 | 01 | 1 | AIML-01 | integration | `python -m app.ml.train --mode combined --max-per-category 1000` | existing | pending |
| 03-02-00 | 02 | 2 | AIML-04 | unit | `pytest tests/test_ml_evaluation.py --collect-only` | W0 (created by task) | pending |
| 03-02-01 | 02 | 2 | AIML-04 | unit | `pytest tests/test_ml_evaluation.py -x` | created by 03-02-00 | pending |
| 03-02-02 | 02 | 2 | AIML-03 | manual + automated | `npx tsc --noEmit && grep -l ConfidenceBadge src/app/dashboard/documents/page.tsx src/app/dashboard/search/page.tsx src/app/dashboard/upload/page.tsx` | existing | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_ml_evaluation.py` — test evaluation API endpoint returns valid JSON with confusion matrix, per-category metrics (created by Plan 03-02, Task 0)
- [ ] `backend/tests/conftest.py` — shared fixtures (verify existing or create)
- [ ] Verify pytest is configured to find tests in `backend/tests/`

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Confidence badge colors | AIML-03 | Visual UI element | Upload document, verify green (>80%), yellow (50-80%), red (<50%) badge colors |
| Evaluation report accessible | AIML-04 | End-to-end flow | Navigate to evaluation report page, verify confusion matrix and per-category metrics display |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
