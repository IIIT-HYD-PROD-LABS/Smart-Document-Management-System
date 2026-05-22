# Phase 17: AI Notice Field Extraction (Zero-Shot, BYOK) - Context

**Gathered:** 2026-05-22
**Status:** Draft, awaiting user sign-off
**Author register:** product (compliance app UI, not marketing)

<domain>
## Phase Boundary

**In scope:** A user uploads a notice PDF (or JPG/PNG) and the system extracts the canonical compliance fields from the file using the tenant's own Anthropic or Gemini key (Phase 16 BYOK). When confidence is high enough, the create-notice form is pre-populated with per-field confidence indicators and an inline accept/edit affordance. When confidence is low, the file routes to the existing Phase 10 review queue. The Gmail ingestion path uses the same extractor so behaviour is identical regardless of source.

**Specifically:**

1. New extractor service (`notice_extractor_service.extract_notice_fields`) that calls the Phase 16 provider adapter with a notice-specific prompt and returns structured fields plus per-field confidence.
2. Schema additions on `compliance_notices` for the extraction artefact (`extracted_fields jsonb`, `extraction_confidence numeric`, `extracted_by_provider text`, `extracted_at timestamptz`, `extraction_status text`).
3. New permission `NOTICE_AI_EXTRACT` registered in the compliance permission registry. Gated to roles that can already create or edit notices.
4. Three new endpoints under `/api/compliance/notices`: extract-preview (no persistence), get-extraction, accept-extraction.
5. Celery wiring: `process_document_task` calls the extractor when the document is attached to a notice, and writes the result back to that notice row.
6. Gmail wiring: `process_classified_email` calls the same extractor before creating the auto-routed notice, populating fields directly.
7. Confidence-based routing: average per-field confidence at or above 0.75 writes fields to the notice; below routes to `NoticeReviewQueue` with the same artefact attached.
8. Upload-first frontend flow: the `/dashboard/compliance/notices/new` page leads with a dropzone; once extraction returns, the form fills with confidence badges; each field has accept, edit, and discard affordances.
9. Audit trail: every extraction call writes one `audit_log` row (action `NOTICE_AI_EXTRACT`) with provider, model, token count, latency, body SHA-256, average confidence. No raw PDF text or extracted field values in audit args.
10. End-to-end smoke (`scripts/smoke_phase17_v20.py`) covering upload, extract, accept, audit, RLS isolation.

**Out of scope (explicitly):**

- Supervised fine-tuning, spaCy NER bake-off, BERT bake-off. Those remain Phase 10 v2.1 work. Phase 17 ships zero-shot LLM extraction first because BYOK already exists.
- Tabular extraction (annexure tables with line items). v2.0 extracts headline fields only. Line-item tables are Phase 12 v2.1 territory (response drafting / reconciliation).
- Multi-page notice classification beyond the first 4000 characters. The v1.0 `_build_extraction_prompt` truncates to 4000 chars today; Phase 17 keeps that ceiling and documents it.
- Handwritten notice extraction. Server-side OCR runs unchanged; if Tesseract returns garbage, extraction will return low confidence and the file goes to the review queue.
- New AI provider integrations. Phase 17 uses only the Anthropic and Gemini adapters already registered in Phase 16.
- Bulk re-extraction of historical notices. A migration backfill on the existing notice rows is a separate v2.1 backlog item, not in this phase.

</domain>

<decisions>
## Implementation Decisions

### Extractor service

- **D-01:** Add the extractor as a new function `extract_notice_fields(db, notice_id, text)` inside `backend/app/compliance/services/ai_service.py`, alongside the existing `summarize_notice` and `recommend_notice_actions`. Reuses `build_provider`, `AICredential` lookup, the scope-locked SYSTEM prompt, and the `OUT_OF_SCOPE` sentinel. No new provider abstraction.
- **D-02:** A new file `backend/app/compliance/services/notice_extraction_prompt.py` holds the compliance-specific prompt template, field schema, and JSON envelope. Keeps `ai_service.py` thin; lets prompt evolution live in one place.
- **D-03:** Extraction returns the envelope `{ fields: { <key>: {value, confidence, source_span} }, average_confidence, model, tokens_in, tokens_out, latency_ms }`. `source_span` is the original substring the model claims it pulled the value from. Renders the "show me where" pop-over in the UI cheaply.
- **D-04:** Field schema (v2.0): `notice_number`, `authority` (one of GST, IT, MCA, RBI, SEBI), `notice_type`, `issued_date` (ISO 8601), `response_deadline` (ISO 8601), `tax_demand` (number), `interest` (number), `penalty` (number), `total_liability` (number), `taxpayer_name`, `gstin`, `pan`, `cin`, `legal_sections` (array of strings). Anything else the model returns is dropped silently. The list mirrors Phase 9 LIFE-03 form fields exactly so accept-extraction can map field name to column directly.
- **D-05:** The prompt instructs the model to omit fields it cannot find rather than emit a low-confidence guess. This trades recall for precision: a missing field is better than a wrong one, because a wrong number on a tax-demand line propagates into risk scoring and alerting.

### Routing and confidence

- **D-06 [REVISED 2026-05-22 per user sign-off]:** Routing gate is conjunctive, not a single average. Auto-apply requires ALL THREE: (a) average per-field confidence across returned fields at or above 0.85, (b) `notice_number` confidence at or above 0.85, (c) `authority` confidence at or above 0.85. Any of the three failing routes to the review queue. Critical-field gating prevents the case where the model returns 0.95 on five soft fields and 0.6 on `notice_number`, yielding a high average that masks a wrong identifier. Mirrors Phase 10 CLASS-04 in spirit (review-queue at low confidence) but raised because the failure cost of a wrong notice_number is high.
- **D-07:** Routing is computed over only the fields the model returned, not the full schema. If the model returns just `notice_number` and `issued_date` at 0.92 confidence each, that counts as 0.92 average, not 0.92 multiplied by coverage. Coverage is a separate metric surfaced in the UI but not used for the routing gate.
- **D-08 [REVISED 2026-05-22]:** Per-field confidence below 0.75 is rendered amber in the UI; below 0.55 is rendered red and pre-flagged as "needs review". User can still accept any field at any confidence; rendering is advisory. Thresholds shifted up with D-06 so the UI visual language matches the stricter routing posture.
- **D-09:** When extraction fails entirely (provider error, network timeout, OUT_OF_SCOPE sentinel), the document is still saved, the notice is still created if Gmail path, and an `extraction_status` of `failed` is recorded. The user sees an "AI extraction unavailable, fill manually" banner on the form. Failures are non-fatal because the file is the source of truth.

### Persistence

- **D-10:** Five new columns on `compliance_notices`: `extracted_fields jsonb null`, `extraction_confidence numeric(3,2) null`, `extracted_by_provider text null`, `extracted_at timestamptz null`, `extraction_status text null check (extraction_status in ('pending','completed','failed','accepted','superseded'))`.
- **D-10a [NEW 2026-05-22 during Plan 17-02 prep]:** `ner_extracted_fields` (added in Phase 10) is NOT reused. Phase 10 stores regex hits plus SHAP risk top factors there with the shape `{notice_number, dates, amounts, risk_top_factors}`. Phase 17's envelope is the D-03 shape `{fields: {field: {value, confidence, source_span}}, average_confidence, model, ...}`. Different lifecycles, different owners, different update paths. Cohabiting them in one column would force every reader to branch on shape. Two columns, one truth each.
- **D-11:** Accept-extraction copies the chosen fields into the canonical notice columns AND sets `extraction_status='accepted'` AND writes one audit row per accepted field with the original value, the accepted value, and the difference (if user edited inline). Preserves the manual-override paper trail compliance heads will want.
- **D-12:** Re-uploading a file (today, first-upload-wins) does NOT re-trigger extraction for the canonical notice. The new file gets its own extraction and lands in the activity timeline as `extracted_supplementary`, viewable but not auto-applied. Prevents accidental overwrite of already-accepted fields.

### BYOK contract

- **D-13:** Extraction counts as TaxSync work and is permitted by the Phase 16 scope-locked SYSTEM prompt. No prompt changes needed for scope; only the user-message prompt changes.
- **D-14:** If the tenant has no `AICredential` row, the extract endpoints return HTTP 412 (Precondition Failed) with a structured error pointing to `/dashboard/settings/ai-credentials`. The upload itself still succeeds. The compliance head can fill the form manually.
- **D-15:** Token budget cap per extraction call: 8k input tokens, 2k output tokens. The 4000-char input truncation (carried from v1.0 `_build_extraction_prompt`) keeps us safely under the input cap on Anthropic and Gemini both.

### Audit and PII

- **D-16:** Audit row schema: `actor_id`, `action='NOTICE_AI_EXTRACT'`, `target=notice_id`, `args={provider, model, tokens_in, tokens_out, latency_ms, average_confidence, fields_returned (key list only), body_sha256}`. No raw text, no extracted values. Mirrors Phase 15 D-35/D-36 redaction pattern.
- **D-17:** Acceptance audit (separate row per field) carries `args={field, original_value_sha256, accepted_value_sha256, was_edited (bool)}`. Hash both values so tampering after the fact is detectable without ever storing the literal value in the audit log.
- **D-18:** Phase 9 immutability trigger applies automatically to both audit row types. No new trigger or REVOKE work.

### Endpoints

- **D-19:** `POST /api/compliance/notices/extract-preview` accepts a multipart file, runs storage, OCR, extraction synchronously (no notice row, no document row persisted). Returns the extraction envelope. Used by the upload-first form so the user sees results before clicking Save. Rate limited to 12 per minute per tenant (same limiter Phase 16 uses).
- **D-20:** `GET /api/compliance/notices/{id}/extraction` returns the persisted extraction artefact for a notice, scoped by RLS. Used by the detail page to render the provenance side panel.
- **D-21:** `POST /api/compliance/notices/{id}/accept-extraction` takes a list of `{field, value, accept_as_is (bool)}` and writes the accepted fields onto the canonical notice columns. Permission `NOTICE_AI_EXTRACT` plus `NOTICE_UPDATE`. Returns the updated notice.
- **D-22:** Preview endpoint does NOT depend on a notice id existing first. It is a stateless extraction. This is what makes the upload-first UX possible: the user uploads, sees fields, then clicks Save to mint the notice row. The notice id is generated in the Save call, which carries both the file and the accepted-fields payload.

### Celery and Gmail wiring

- **D-23:** `process_document_task` checks `document.notice_id is not null` at the end of OCR. If true, it calls the extractor service synchronously (within the same task, not a new one). Result writes to `compliance_notices.extracted_fields` and friends for that notice. If `notice.document_id` matches the document being processed (first-upload-wins case), the routing gate runs: high confidence keeps the notice in `Received`, low confidence enqueues a `NoticeReviewQueue` row with reason `low_confidence_extraction`.
- **D-24:** Gmail `process_classified_email` calls the extractor BEFORE creating the `ComplianceNotice`. The extracted fields are passed into the create call. The audit row for the AI extraction is written first; the notice creation audit row references it via `args.extraction_audit_id`.
- **D-25:** Both wirings share the same routing gate code in a new helper `extraction_routing_service.route_or_apply(notice, extraction)`. Single decision surface, both call sites use it, easy to evolve.

### Frontend

- **D-26:** Rewire `/dashboard/compliance/notices/new` from manual-only to upload-first. Two states on the same page: (a) empty, dropzone full-bleed; (b) post-extraction, form filled with per-field confidence badges, dropzone collapses to a small "uploaded" chip. No second page, no modal.
- **D-27:** New component `ExtractionPreviewForm` replaces the bulk of the current `new/page.tsx` form. Renders the existing form fields but each one is wrapped in an `ExtractedFieldWrapper` that shows the confidence badge, source span on hover, accept/edit/discard buttons. When user edits, the field flips to "user-edited" state and the original extraction is kept in a hidden field for the audit row.
- **D-28:** `NoticeAISection.tsx` already exists for Phase 16 summary/actions on the detail page. Add a small "View extraction provenance" disclosure that hits `GET /extraction` and renders provider + model + confidence + accepted vs auto fields. No new top-level component on the detail page.
- **D-29:** Loading states: the extract-preview call has a P95 around 4 to 8 seconds across Anthropic Sonnet and Gemini Flash on a typical 2-page GST notice. The UI shows a determinate progress bar (uploading), then an indeterminate "Extracting fields with <provider> <model>" state, then a soft fade-in of the populated form. No spinner-only states.
- **D-30:** Empty-state and error-state copy lives in the same component. If the tenant has no AI credential, the dropzone sits next to a quiet inline notice ("Connect an AI provider in settings to enable extraction. You can still upload and fill the form manually."). No modal, no toast.

### Tests and smoke

- **D-31:** Wave 0 RED stubs: 8 backend pytest files, 3 frontend vitest files. Backend covers extractor unit, prompt envelope, Celery integration, Gmail integration, accept-extraction service, RLS isolation, BYOK auth failure, audit redaction. Frontend covers dropzone, post-extraction form, accept-individual-field, edit-individual-field, discard-individual-field, save-with-accepted-fields, empty-credential banner.
- **D-32:** Smoke (`scripts/smoke_phase17_v20.py`) uses a real Anthropic Sonnet call against a fixture GST notice PDF, asserts the 4 highest-confidence fields are present, persists, accepts them, and verifies the audit chain. Skipped automatically in CI if `ANTHROPIC_API_KEY_SMOKE` is unset.

### Structural validation (NEW per user sign-off 2026-05-22)

- **D-33:** Extracted values pass through `notice_extraction_validator.validate_and_score(envelope)` before the routing gate. Per-field rules: `gstin` matches the Phase 9 GSTIN regex (15 chars, state code, PAN embedded, checksum), `pan` matches the Phase 9 PAN regex, `cin` matches CIN regex, `issued_date` and `response_deadline` parse as ISO 8601 dates AND deadline is later than issued_date, `tax_demand`/`interest`/`penalty`/`total_liability` are non-negative numbers, `total_liability` (if returned) equals tax_demand plus interest plus penalty within 1 INR tolerance. Any field that FAILS its rule has its model-reported confidence multiplied by 0.5 before contributing to the D-06 averages. The original confidence and the post-validation confidence are both kept in the envelope so the UI can show "structurally suspect" badges distinct from "model-uncertain" ones.
- **D-34:** Validation failures are surfaced per-field in the UI with a small icon next to the confidence badge. Hover copy explains the failure ("GSTIN does not match the 15-character format" / "deadline is earlier than issued date"). User can still accept the field as-is; the acceptance audit row records both the original LLM confidence, the post-validation confidence, and the validation failure reason.

### Claude's discretion

- Prompt template wording (within the D-04 field schema and D-05 precision-over-recall rule).
- Confidence threshold finer than the 0.6 amber / 0.4 red split (subject to the 0.75 routing gate from D-06).
- Visual treatment of the per-field confidence badge (chip vs dot vs ring) within impeccable's product register and the existing `ConfidenceBadge.tsx`.
- Skeleton shape during extraction loading.
- Exact migration ordering (must come after head 0030; sequence number assigned at write time).
- Whether to introduce a typed `ExtractionEnvelope` Pydantic schema or stay with a TypedDict (typed schema is preferred for OpenAPI surface).

</decisions>

<plan_map>
## Plan Map (7 waves)

| Plan | Wave | Scope | Gate |
|---|---|---|---|
| 17-01 | 0 | Test infrastructure: 8 backend + 3 frontend stubs, fixtures, frozen contracts | RED |
| 17-02 | 1 | Migration 0031, permission registration, Pydantic schemas | GREEN at schema level |
| 17-03 | 2 | `extract_notice_fields` service, prompt module, routing helper | Wave 0 backend service tests flip GREEN |
| 17-04 | 3 | Celery wiring + Gmail wiring + first-upload-wins guard | Wave 0 integration tests flip GREEN |
| 17-05 | 4 | 3 router endpoints, gating, rate limit | Wave 0 router tests flip GREEN |
| 17-06 | 5 | UI: upload-first form rewrite, `ExtractionPreviewForm`, provenance disclosure | Wave 0 vitest stubs flip GREEN; impeccable shape run completed first |
| 17-07 | 6 | Smoke script, README update, ROADMAP table update, STATE.md update | Phase ships |

</plan_map>

<success_criteria>
## Success Criteria (what must be TRUE to call Phase 17 shipped)

1. A user uploads a GST DRC-01 PDF on `/dashboard/compliance/notices/new` and within 10 seconds sees the form pre-populated with at least notice_number, authority, issued_date, and response_deadline, each carrying a visible confidence indicator.
2. Each pre-populated field can be accepted as-is, edited inline, or discarded before Save. Edits are recorded in the audit log against the same notice id.
3. A low-confidence extraction (average below 0.85, OR notice_number below 0.85, OR authority below 0.85) routes the upload to the existing Phase 10 review queue with reason `low_confidence_extraction`, surfacing on `/dashboard/compliance/review-queue` for a reviewer. A structurally invalid GSTIN, PAN, CIN, or date counts as a confidence downgrade per D-33 and is visible on the reviewer's screen.
4. Gmail-ingested notices arrive with extracted fields already populated and the same provenance disclosure is visible on the notice detail page.
5. Tenants without an `AICredential` configured see a quiet inline banner and can still upload and fill manually; no 500s, no broken state.
6. Every extraction call writes exactly one `audit_log` row with action `NOTICE_AI_EXTRACT` containing provider, model, latency, average confidence, and body SHA-256 (no raw text, no extracted values).
7. RLS isolation holds: an extraction artefact on a notice in client A is invisible to a user authenticated against client B.
8. The Phase 9 audit immutability trigger refuses any UPDATE or DELETE attempt on extraction audit rows (verified by an automated test, not a manual probe).
9. Smoke script (`scripts/smoke_phase17_v20.py`) passes end to end against a real provider call.

</success_criteria>

<requirements>
## Requirements

These map onto the active `.planning/PROJECT.md` block "Notice Retrieval & Classification" item "NER extraction (notice number, date, authority, deadline, penalty, legal sections)" which moves from `[ ]` to validated under this phase.

- **EXTRACT-01:** Per-tenant BYOK call (Phase 16 AICredential reused)
- **EXTRACT-02:** Compliance-specific extraction schema (14 fields, D-04)
- **EXTRACT-03:** Confidence-based routing gate at 0.85 average AND notice_number and authority both at 0.85+ (D-06)
- **EXTRACT-03b:** Structural validation (GSTIN, PAN, CIN, ISO dates, liability arithmetic) downgrades confidence on shape failure (D-33, D-34)
- **EXTRACT-04:** Upload-first UX with per-field accept / edit / discard (D-26..D-28)
- **EXTRACT-05:** Synchronous extract-preview endpoint (D-19, D-22)
- **EXTRACT-06:** Celery integration on `process_document_task` (D-23)
- **EXTRACT-07:** Gmail integration on `process_classified_email` (D-24)
- **EXTRACT-08:** Audit row per extraction call, PII-redacted (D-16)
- **EXTRACT-09:** Per-field acceptance audit with before/after hashes (D-17)
- **EXTRACT-10:** Tenant-without-credential graceful path (D-14, D-30)
- **EXTRACT-11:** RLS isolation on extraction artefact (Phase 9 inheritance)
- **EXTRACT-12:** Immutability of extraction audit rows (Phase 9 inheritance)

</requirements>

<dependencies>
## Dependencies

- **Phase 9:** RBAC permission registry, audit log, RLS, PII encryption helper.
- **Phase 10:** `NoticeReviewQueue` (used by the low-confidence routing branch).
- **Phase 15:** `process_classified_email` is the integration surface for the Gmail path.
- **Phase 16:** `AICredential`, `build_provider`, scope-locked SYSTEM prompt, `ai_service.py` module.
- **v1.0:** `storage_service.save_file`, `process_document_task`, OCR (`backend/app/services/llm_service.py` for the response-parsing helper `_parse_llm_response`).

</dependencies>

<risks>
## Risks

- **R-01:** Provider response drift. Anthropic or Gemini changes its JSON output format; extraction silently degrades. **Mitigation:** strict envelope validation in `_parse_llm_response`, smoke pinned to a specific model version, alert on parse-failure rate above 5 percent over a rolling 100 calls.
- **R-02:** Cost runaway. A user uploads a 50-page brochure misrouted as a notice; tokens explode. **Mitigation:** 4000-char input truncation (D-15), per-tenant rate limit (D-19), per-call token cap (D-15).
- **R-03:** False high-confidence. The model returns plausible-but-wrong values with 0.9 confidence. **Mitigation:** D-05 precision-over-recall prompt; D-17 immutable acceptance audit forces a paper trail when humans accept; v2.1 backlog item: cross-check extracted GSTIN/PAN against the Phase 9 regex validator and downgrade confidence on mismatch.
- **R-04:** OCR garbage in, garbage out. Tesseract returns a noisy string for a scanned notice; extraction confidence tanks. **Mitigation:** low confidence routes to review queue (D-06); reviewer sees the raw OCR and can correct or re-upload a cleaner scan.
- **R-05:** UI confusion. Users do not understand why some fields are pre-filled and others are not. **Mitigation:** D-30 inline copy on the form; provenance disclosure on the detail page; per-field confidence badge with hover text explaining the score.

</risks>

<v21_deferrals>
## Explicit v2.1 Deferrals

- Supervised NER / BERT bake-off (Phase 10 v2.1) remains deferred. Phase 17 ships the zero-shot LLM path first because BYOK exists; a future supervised path can swap the extractor implementation behind the same service interface.
- Tabular line-item extraction.
- Bulk re-extraction of historical notices.
- Cross-validation of extracted GSTIN/PAN against Phase 9 regex validators.
- Active-learning loop where corrected fields become training data.

</v21_deferrals>

<canonical_refs>
## Canonical References

- Phase 16 BYOK shipped 2026-05-08 (memory: `project_ai_byok_phase16.md`); scope-locked SYSTEM prompt: `backend/app/compliance/services/ai_service.py:1-80`.
- Phase 9 audit immutability (memory: `project_audit_logs_trigger.md`); trigger raises on UPDATE/DELETE.
- Current manual notice form: `frontend/src/app/dashboard/compliance/notices/new/page.tsx:14-77`.
- Current upload handler: `backend/app/compliance/routers/notices.py:619-710`.
- Current Gmail ingestion handoff: `backend/app/email/services/ingestion_service.py:249`.
- Phase 10 review queue: `backend/app/compliance/services/review_queue_service.py`.
- v1.0 LLM extraction precedent (DMS categories): `backend/app/services/llm_service.py:14-60`.
- Project conventions: `.planning/PROJECT.md`; ROADMAP table in `.planning/ROADMAP.md`.

</canonical_refs>
