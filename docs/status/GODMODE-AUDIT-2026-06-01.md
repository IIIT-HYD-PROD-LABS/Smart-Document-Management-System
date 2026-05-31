# GODMODE Audit and Fix Sweep, 2026-06-01

Opus 4.8 (1M context) end to end audit of the notice upload, LLM field
extraction, and compliance workflow, plus a frontend UX and accessibility
pass. Scope driven by the reported symptom that "notice file upload, LLM
extraction to fill the notice fields, and the compliance workflow end to end"
were not working reliably.

Method: a 5 lane parallel deep read (extraction correctness, compliance
workflow integrity, security, frontend wiring, frontend design) followed by an
adversarial verification pass on every critical and high finding (each claim
handed to a skeptic agent instructed to refute it against the actual code).
0 of the 5 high findings were refuted. Live reproduction was performed against
an ephemeral Postgres 15 for the data layer findings.

## Findings and fixes

### High severity

1. Accept extraction wrote raw values onto typed columns (HTTP 500).
   `POST /notices/{id}/accept-extraction` copied `item.value` (typed `Any`)
   straight onto `Numeric(18,2)` money columns and `Date` columns via
   `setattr`, with no coercion. A currency formatted amount ("Rs. 1,45,000",
   a comma grouped number, a "1.45 lakh" phrase) or a DD-MM-YYYY date (all
   routine in OCR of Indian notices, even though the prompt asks for ISO and
   plain numbers) reached psycopg2 as a raw string and raised
   `StatementError` or `DataError`. The commit guard caught only
   `(IntegrityError, OperationalError)`, so the request returned an unhandled
   500.
   Fix: a single coercion module, `extraction_coercion.py`, normalizes amounts
   (strips currency tokens and grouping, honors lakh and crore multipliers,
   bounds to Numeric(18,2)) and dates (ISO plus common Indian formats) and
   raises `CoercionError` on anything unrepresentable. The endpoint now coerces
   before the write, returns a clean 422 on a bad value, and the commit guard
   was broadened to `(IntegrityError, OperationalError, DataError,
   StatementError)` as a defense in depth backstop.

2. Detail page upload extraction never filled the notice fields.
   The async upload pipeline (FileDropzone, `POST /notices/{id}/upload`, the
   Celery task, `apply_extraction_to_notice`) persisted the extraction
   envelope only into the JSONB and metadata columns. It never wrote the
   canonical editable columns, and the detail page had only a read only
   provenance disclosure with no accept control. A notice whose file was
   uploaded from the detail page showed "Extracted, awaiting acceptance"
   forever with the fields left blank. This was the primary reported symptom.
   Fix: `apply_extraction_to_notice` now back populates the canonical columns
   on a high confidence "apply" decision, using the same coercion as the accept
   endpoint, and flips `extraction_status` to "accepted". The policy is fill
   don't clobber: a confident extraction never overwrites a value a human
   already entered. Per field coercion failures are swallowed so one bad value
   never aborts the whole apply in the Celery worker. The accept extraction
   replay path opts out (`fill_columns=False`) so the user reviewed items stay
   authoritative.

3. Maker equals checker bypass in the response approval chain.
   `apply_approval` enforced "the drafter cannot approve their own response"
   using only `response.created_by_user_id`, which records the response shell
   creator. The substantive draft author is recorded on
   `NoticeResponseVersion.created_by_user_id`, which the approval path never
   consulted. When two staff collaborate (shell created by user A, reply body
   written by user B), user B could approve their own drafted content, since B
   was neither the shell creator nor a prior stage approver. The
   `ca_consultant` role holds both drafting and all approval permissions, so it
   was reachable end to end.
   Fix: a new R1.1b guard disqualifies any actor who authored any version of
   the response, alongside the existing shell creator and prior stage walls.

4. Unbounded multipart read on the upload paths (memory exhaustion DoS).
   `POST /notices/{id}/upload` and `POST /notices/extract-preview` read the
   entire multipart body into memory in one unbounded call. The global body
   size middleware exempts multipart, and there is no proxy body cap, so any
   authenticated tenant member could buffer an arbitrarily large file and OOM
   the worker. extract-preview additionally ran synchronous OCR on the same
   bytes.
   Fix: a shared `_read_validated_upload` helper streams the body in 1 MB
   chunks and aborts with 413 once `settings.MAX_FILE_SIZE_MB` is exceeded,
   before any save or OCR work, mirroring the existing documents.py pattern.

### Medium and low severity

5. Calendar deadline pills failed WCAG-AA contrast. The day cell pills used the
   bright authority icon hue as the 10px text color over a tint of the same
   hue (2.1:1 to 3.7:1 across authorities). Fix: the AA calibrated `.text`
   token now drives the foreground; the bright hue stays on the background and
   border only, matching the `AuthorityBadge` contract.

6. Gmail auto create dropped dates and amounts. The Gmail ingestion path copied
   only notice_number and authority onto the new notice, leaving
   response_deadline and the money fields NULL, so deadline alerts fired
   against nothing. Fixed transitively by finding 2: `apply_extraction_to_notice`
   now fills those columns before `process_notice_intake` reads the deadline.

7. No magic byte validation on compliance uploads. The two upload paths trusted
   the client spoofable `content_type` with no content check, and an in code
   comment falsely claimed `save_file` validated magic bytes. Fix:
   `_read_validated_upload` now calls `validate_magic_bytes` against the
   declared type; the false comment was corrected.

8. extract-preview inherited the 30s axios timeout. A slow but still succeeding
   LLM extraction aborted client side and dropped the user to manual entry with
   a misleading "timeout" toast. Fix: a 120s per call timeout.

9. NoticeTable selection checkboxes were 14px, under the 24px WCAG 2.5.8 target
   floor. Fix: each checkbox is wrapped in a 24px `touch-target` hit area.

10. The reclassify modal had no Escape to close and no focus management. Fix:
    Escape now closes it (unless a save is in flight), focus moves into the
    dialog on open and restores to the trigger on close (parity with
    ClientSwitcher).

11. ExtractedFieldRow buried the validation reason in a title tooltip
    (keyboard and screen reader inaccessible). Fix: the validation failure is
    now visible inline below the input, and the confidence chip is 11px.

## Verification

- Backend: new and existing unit tests for the coercion module, the accept
  endpoint (currency and non ISO date now succeed, garbage returns 422), the
  auto apply fill behavior, the version author SoD guard, and the upload size
  and magic byte guards. 60 targeted tests green; the extraction integration
  suite (celery and gmail) green in the Redis equipped environment. Two
  apparent failures in an isolated container were environmental (no Redis
  reachable for the Celery dispatch), confirmed green where Redis exists.
- Frontend: `tsc --noEmit` clean, `next lint` clean on all changed files (no
  new warnings).
- Frontend image rebuilt and a design review pass run against the live app.

## Files changed

Backend:
- `app/compliance/services/extraction_coercion.py` (new)
- `app/compliance/routers/notices.py` (accept coercion, broadened guard,
  `_read_validated_upload`, magic bytes, false comment corrected)
- `app/compliance/services/extraction_routing_service.py` (auto apply fill,
  `fill_columns` flag)
- `app/compliance/services/response_service.py` (version author SoD guard)
- `tests/compliance/extraction/test_accept_extraction.py`,
  `tests/compliance/extraction/test_extraction_coercion.py` (new),
  `tests/compliance/extraction/test_notice_upload_validation.py` (new),
  `tests/test_response_service.py`

Frontend:
- `src/app/dashboard/compliance/calendar/page.tsx`
- `src/app/dashboard/compliance/review/page.tsx`
- `src/components/compliance/NoticeTable.tsx`
- `src/components/compliance/ExtractedFieldRow.tsx`
- `src/lib/api/compliance.ts`
