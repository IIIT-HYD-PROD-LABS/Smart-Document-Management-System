# Ingest Pipeline Audit and Adversarial Verification

**System:** Smart Document Management and Compliance System (TaxSync)
**Date:** 2026-07-16
**Base commit:** `7957d41` on `main` ("fix bugs found in the end-to-end audit of the ingest pipeline")
**Scope:** The email, Google Drive, gov-portal, OCR/ML, and notice-intake feature code (the surfaces recently built with external assistant models), plus an adversarial re-review of the `7957d41` fix commit itself.

## 1. What this pass covered

The `7957d41` commit was the remediation output of a first end-to-end audit of the ingest pipeline. This pass did two things:

1. Adversarially re-reviewed every fix in `7957d41` to confirm it is correct and introduced no regression (imports resolve, no NameError from moved code, IDOR genuinely closed, error signatures correct, no orphaned dead code).
2. Continued hunting for issues the first audit missed, concentrating on the notice-intake dispatch paths where the email, Drive, and portal routes diverge.

## 2. Verification of the 7957d41 fixes

All fixes in the commit were re-checked against the running code and confirmed correct:

| Area | Fix | Verified |
|------|-----|----------|
| Email classifier | Compliance sender regex matches the bare address (email.utils.parseaddr), not the raw `Name <addr>` From header | Empirically: `GST Portal <noreply@cbic-gst.gov.in>` classifies True |
| Email scanner | Rollback in each except handler; content-addressed attachment filenames; SAVEPOINT-guarded insert; skip LLM on ignored mail; Redis lock compare-and-delete token | Imports and guards present, correct scoping |
| Drive | client_id from validated membership, not the X-Client-Id header (closes cross-tenant IDOR); orphan file removed on failure | IDOR closed via require_compliance_permission to get_active_membership DB bind |
| Portal | 409 plus orphan-file cleanup on duplicate filename; removed the redundant in-request notice intake | file_path bound before the flush, cleanup safe |
| Extraction routing | Recognize PORTAL- placeholders; stop stamping canonical columns from a review-queue (sub-threshold) extraction | Envelope still parked unconditionally, columns not stamped on review path |
| OCR/ML | docx decompression cap (zip bomb); image and page dimension probe before decode/render (OOM); per-task tenant-context reset in the document worker; dead code removed | Correct constants and error reasons, ContextVar isolation via copy_context |

The extraction-routing review path (item that most directly protects the deadline calendar) was traced in full: `_stamp_extraction_fields` writes `notice.extracted_fields = envelope` unconditionally, then only the apply path stamps canonical columns. A sub-threshold extraction therefore parks its full envelope for human review with no data loss and never drives a real T-7/T-3/T-1 alert.

## 3. New findings and fixes (this pass)

### 3.1 Drive: double notice intake with a classification race (fixed)

**File:** `app/drive/router.py`

The Drive import path dispatched `process_document_task.delay(doc.id)` (which runs the unified notice pipeline `after_document_intelligence` and ends in `process_notice_intake`) **and** also called `process_notice_intake(notice_id, notice_deadline)` explicitly in the request. The explicit call passed the pre-OCR deadline (always None for a freshly created Drive notice), while the pipeline call runs after OCR with the extracted deadline.

Consequences:
- The notice was classified twice. The explicit call classified an empty pre-OCR notice; the pipeline re-classified after OCR with real text. Under adversarial worker timing the empty-notice classification could commit last and overwrite the good risk score.
- The explicit call was strictly inferior (no deadline) and redundant.

The `7957d41` commit had already identified this exact redundancy for the portal route and removed portal's explicit intake, but for Drive it only moved the call after commit rather than removing it. This pass removes Drive's explicit `process_notice_intake` call so Drive mirrors portal: the queued task is the sole intake trigger, running after OCR with the extracted deadline. The two now-unused `notice_deadline` assignments were removed with it.

Idempotency note: even before this fix the double dispatch could not create duplicate rows. Risk-score persistence is a last-write-wins column update, and `enqueue_low_confidence` is a Postgres UPSERT on the `notice_id` unique constraint. The defect was the wasted work and the last-writer race, not row duplication.

No-text note: like portal, Drive now relies on the pipeline, which skips intake when OCR yields no text. Such notices are recovered by the daily `recompute_all_risk_scores` cron, the documented recovery path.

### 3.2 Routing-gate tests were not hermetic (fixed)

**File:** `tests/compliance/extraction/test_routing_gate.py`

`route_or_apply` reads `settings.EXTRACTION_AVG_GATE` and `settings.EXTRACTION_CRITICAL_GATE` at call time. The code default is 0.85, but a deployment can lower it (the local stack sets both to 0.6 for local LLMs that under-report confidence). The gate-logic tests asserted 0.85 behaviour without pinning the thresholds, so they produced false failures under any environment that tunes the gate (four failures in the running dev container).

This is a test-quality defect, not a code regression: with the thresholds at the 0.85 default all five tests pass, confirming the gate logic is correct. The fix adds an autouse fixture that pins both thresholds to 0.85 for this file, so the logic tests are deterministic regardless of deployment tuning. Verified: all five pass under the container's ambient 0.6 override after the fix.

The 0.6 production/dev tuning of the gate is a deliberate deployment choice and is left as-is. Operators running a well-calibrated hosted model may want to raise it back toward 0.85.

## 4. Verification

- Full FastAPI app imports cleanly with the Drive change (drive router mounts into the app with no import-time error).
- `tests/test_notice_pipeline.py`: 3 passed. Confirms the invariant the Drive fix relies on: the pipeline runs extraction then intake with the extracted deadline, and skips intake on no text.
- `tests/compliance/extraction/test_routing_gate.py`: 5 passed under the ambient 0.6 override after the hermeticity fix.
- `tests/compliance/extraction/test_extraction_coercion.py`, `tests/test_extraction_failures.py`, `tests/test_email_routing.py`: 56 passed. No other no-DB extraction test carried the same latent gate assumption.
- Baseline: `7957d41` recorded 756 backend tests passing on a fresh DB. This pass changed one production line by deletion in an endpoint with no dedicated test, plus one test-only fixture, so the fresh-DB count is unchanged.

## 5. Deferred and tracking items

- **EM2 (email):** the ingestion log is committed before side effects complete. A `fully_processed` flag plus a reprocess path would make a mid-processing crash recoverable. Not yet implemented.
- **M4 (OCR):** a truncated scanned PDF surfaces `ai_extraction_status = incomplete_scanned_pdf`, but the page-truncation detection itself is a documented tracking item pending broader page-budget handling.
- **D4 (Drive):** one lower-severity Drive item from the first audit remains unresolved and is carried forward.
- **Campus DB migration:** the Drive source requires `documents.source = 'google_drive'`, added by migration `0041`. The campus database is at `0040`. Run `alembic upgrade head` before Drive import is used in the deployed environment.

## 6. Deploy status

- Local stack: healthy (backend, celery, compliance worker, db, redis, frontend all up).
- The Drive fix and the test fixture are in the monorepo working tree at the time of writing; propagating them to `gh-backend/staging` (flattened deploy repo) follows the established re-flatten diff-apply path, never a `push main:staging`.
- The prod backend remains dependent on the server-side Jenkins "Deploy to Remote Server" stage actually running the built image on `10.2.8.73:8025` with `--env-file .env.prod`; that stage is executed by the deploy team and cannot be verified from this workstation.
