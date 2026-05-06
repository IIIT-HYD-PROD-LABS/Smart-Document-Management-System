# Phase 12: Response Drafting + Evidence Management - Context

**Gathered:** 2026-05-05 (seed scope; awaiting `/gsd:discuss-phase 12` refinement)
**Status:** CONTEXT seeded

<domain>
## Phase Boundary

**In scope:** Users draft, review, approve, and assemble complete notice
responses — including LLM-generated drafts, GST reconciliation exhibits,
linked DMS evidence, and a searchable regulation library — without
leaving the compliance system.

**Specifically:**
1. Notice response template library — 20+ templates (one per common GST
   DRC-01, IT 143(2)/142(1), MCA SCN under §454 use-case) with variable
   substitution + Phase 5 LLM service for free-form sections.
2. Versioned response drafts — every save creates a snapshot; rollback is
   a O(1) operation.
3. Multi-stage approval workflow — Drafter → Reviewer → Legal → CFO. Each
   stage approval/rejection is recorded in the immutable audit log.
4. Evidence package builder — attach DMS documents to notice responses,
   merge into a single PDF with auto-generated TOC.
5. GST ITC reconciliation engine — upload GSTR-2A/2B + GSTR-3B JSON, get
   mismatch report (blocked credits under §17(5), invoice-level diff).
6. Regulation library — searchable corpus of GST Act, IT Act, Companies
   Act, FEMA, SEBI, CBDT/CBIC circulars; per-section regulation-to-notice-type mapping.
7. Auto-suggested evidence checklist per notice type.

**Out of scope:**
- Direct submission to government portals — Phase 14 owns that.
- E-signature on responses — defer to v2.1 unless customers request.
- AI hallucination guardrails for LLM drafts — relies on Phase 5 multi-provider fallback already in place; LLM-as-judge cross-check deferred to v3.0.
- OCR of signed-and-scanned responses — out of scope; responses live as structured docs in DMS.

</domain>

<decisions>
## Implementation Decisions (proposed seed; refine via `/gsd:discuss-phase 12`)

### Response drafting (RESP-01..06)
- **D-01:** Templates stored as Jinja2 + Markdown in `backend/app/compliance/templates/responses/{authority}/{type}.md.j2`. Schema enforced via Pydantic `TemplateContext` per template (notice_number, deadline, party_name, legal_sections, etc.).
- **D-02:** LLM enhancements for "free narrative" placeholder via existing Phase 5 multi-provider service (`app/services/llm/extraction_service.py`). Prompts versioned per template.
- **D-03:** Versioning — every PATCH on a draft creates a `notice_response_versions` row (analogous to `document_versions` pattern from v1.0 Phase 7). Rollback restores by writing a new version pointing at the previous content.
- **D-04:** Approval workflow — `notice_response_approvals` table with (response_version_id, role, user_id, decision, reason, created_at). State-machine enforces order: Drafter → Reviewer → Legal → CFO; each approval immutable.
- **D-05:** Status-machine extension — new transition `Submitted` becomes legal only after the latest version has approvals from all required stages.

### Evidence (EVID-01..04)
- **D-06:** `notice_evidence_attachments` join table linking ComplianceNotice ↔ Document. Composite UNIQUE on (notice_id, document_id) prevents double-attaching.
- **D-07:** Evidence merge — generate PDF via `pypdf` + `reportlab` (pinned in requirements.txt). TOC built from notice_number + each attached doc's metadata. Output stored as a new Document with category='response_evidence'.
- **D-08:** Auto-suggested evidence checklist — keyed by `(authority, notice_type_code)`. Lookup table `notice_evidence_checklists` seeded with 20+ rows (e.g. "GST DRC-01" → required: GSTR-1, GSTR-3B, ITC reconciliation report, supplier ledger).

### GST Reconciliation (RECON-01..05)
- **D-09:** Parse GSTR-2A and GSTR-2B JSON files (CBIC official schemas) — both are nested invoice arrays.
- **D-10:** Reconcile against uploaded GSTR-3B JSON or DMS-extracted data; output:
  - Matched invoices (GSTIN + invoice_no + amount within ±₹1)
  - Mismatched (GSTIN matches, amount differs)
  - Missing in 2A (claimed in 3B but no supplier upload)
  - Blocked under §17(5) (manual flagging via UI)
- **D-11:** Reconciliation report stored as Document (category='reconciliation') so it appears in the notice's evidence package.

### Regulation library (REG-01..04)
- **D-12:** Corpus loaded from `backend/app/compliance/regulations/{act}/{section}.md` — Markdown files committed to repo. Searchable via PostgreSQL FTS reusing v1.0 Phase 4 search infrastructure.
- **D-13:** `regulation_section_to_notice_type` mapping table — many-to-many; powers "applicable regulations" surface on notice detail page.
- **D-14:** Version history — git is the version-control backstop. The frontend exposes "view git history" deep links to the GitHub repo for transparency.

### Frontend (UI hint: yes)
- **D-15:** `/dashboard/compliance/notices/{id}/response` — split-pane editor (template variables on left, rendered preview on right) with version timeline.
- **D-16:** `/dashboard/compliance/regulations` — search-first regulation library with section-level deep links.
- **D-17:** `/dashboard/compliance/reconciliation` — wizard for GSTR-2A/2B + 3B upload → mismatch table.
- **D-18:** Approval drawer on notice detail page — per-stage approver chip with "Approve / Reject + reason" inline.

</decisions>

<canonical_refs>
- `.planning/REQUIREMENTS.md` — RESP-01..06, EVID-01..04, RECON-01..05, REG-01..04
- `.planning/phases/09-compliance-foundation/` — notice state machine, audit immutability, RBAC
- `.planning/phases/10-ml-classification-risk-scoring/` — ML pipeline (response templates may consume risk_tier for tone)
- `.planning/phases/11-alerts-and-calendar/` — approval-stage alerts fire via Phase 11 dispatch_alert
- `backend/app/services/llm/extraction_service.py` — multi-provider LLM service (reused for draft generation)
- `backend/app/models/document.py` — versioning pattern reused for response drafts
- `backend/app/services/storage_service.py` — DMS attachment storage
</canonical_refs>

<deferred>
## Deferred to v2.1+
- E-signature integration (DocuSign / SignWell) — defer to v2.1
- AI hallucination guardrails (LLM-as-judge) — v3.0
- OCR-of-signed responses — out of scope indefinitely
- Auto-fill response fields from notice OCR — v2.2 once enough labeled data
</deferred>

## Open Blockers (resolve during `/gsd:research-phase 12`)
1. **Template authoring capacity** — 20+ templates need lawyer/CA review. Who writes? Hours-per-template budget?
2. **GSTR-2A/2B JSON schema versioning** — CBIC has changed the schema 3× in 2024-26; v2.0 must pin to a specific version + emit a clear error on schema mismatch.
3. **Approval chain configuration** — is the 4-stage chain (Drafter → Reviewer → Legal → CFO) hardcoded or per-client `config_overrides`?
4. **Regulation library corpus sourcing** — copy from public CBDT/CBIC PDFs is permissible? IP-clean?
5. **PDF merge library choice** — pypdf vs PyMuPDF (mupdf) vs pdfplumber. Bake-off needed.
