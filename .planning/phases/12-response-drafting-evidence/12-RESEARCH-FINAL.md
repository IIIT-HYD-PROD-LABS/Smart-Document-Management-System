# Phase 12 — Research Final (decisions committed)

**Finalized:** 2026-05-05
**Status:** Decisions locked for v2.0 ship; template library + LLM drafts + PDF merge + ITC reconciliation + regulation library deferred to v2.1

This document closes blockers from `12-CONTEXT.md` and commits to a v2.0
slice that's executable today vs deferrals that require external content
authoring or third-party schema locks.

---

## 1. v2.0 ship: workflow infrastructure only

**Decision:** v2.0 ships the **schema, state machine, and approval workflow
plumbing** — but NOT the content layer (templates, LLM, PDF merge, ITC
recon, regulation corpus). The split protects the milestone from blocking
on lawyer/CA review cycles while still delivering a usable response
workflow that handles the *current* manual-drafting reality at compliance
shops.

**v2.0 ships:**
1. Notice response data model — `notice_responses` (current draft pointer
   + status), `notice_response_versions` (immutable version snapshots),
   `notice_response_approvals` (per-stage approve/reject log)
2. Free-form text editor — Markdown body + structured metadata (subject,
   recipient, response_date)
3. Versioned save — every PATCH on the draft creates a new version row;
   rollback writes a new version pointing at older content
4. Multi-stage approval state machine — Drafter → Reviewer → Legal → CFO,
   each stage gate enforced server-side
5. Evidence link — `notice_evidence_attachments` join table linking
   ComplianceNotice ↔ Document via composite UNIQUE
6. Permission gates — new `NOTICE_RESPONSE_DRAFT`, `NOTICE_APPROVE_LEGAL`,
   `NOTICE_APPROVE_CFO`. NOTICE_APPROVE (Phase 9) covers Reviewer stage.
7. Frontend — `/dashboard/compliance/notices/{id}/response` editor page,
   version timeline, approval drawer with per-stage chip + action button,
   evidence attach surface on notice detail
8. RBAC — Drafter = `staff` + `legal_team`; Reviewer = `compliance_head`;
   Legal = `legal_team`; CFO = `cfo`. CA Consultant has all 4 (most
   permissive role from Phase 9 D-26)
9. Response cannot transition notice to `submitted` without all 4 stages
   approved — wired into `notice_state_machine.py` Phase 9 contract.
10. Audit + activity timeline rows on every approval / rejection / version
    save / evidence attach (Phase 9 AUDIT-02 pattern)

**v2.1 deferred (depends on external authoring or schema lock):**
1. Response template library (20+ Jinja2 + Markdown files per
   authority/type). v2.1 onboarding sprint with lawyer/CA review.
2. LLM draft generation — wires Phase 5 `extraction_service` for
   placeholder fill. Prompt engineering + regression suite required.
3. Evidence package PDF merge with TOC — `pypdf` + `reportlab`
   integration. Defer because TOC generation needs design review.
4. GST ITC reconciliation engine — CBIC has changed GSTR-2A/2B JSON
   schema 3× in 2024-26; v2.0 cannot lock to a moving target. Re-evaluate
   when the next CBIC schema bulletin lands.
5. Regulation library corpus — GST Act, IT Act, Companies Act, FEMA,
   SEBI regs. Need IP-clean source + compliance-team curation effort.
6. Auto-suggested evidence checklist — depends on (4) regulation library
   + (1) template library being authored first.
7. Auto-fill response fields from notice OCR — depends on Phase 10 BERT
   classifier ship (v2.1).

---

## 2. State machine

The 4-stage approval chain is hardcoded in v2.0 (per-client overrides via
`config_overrides` deferred to v2.1). State machine:

```
[draft] ──submit_for_review──▶ [reviewer_pending]
   │                                 │
   │                            approve│reject
   │                                 ▼     │
   └──────reject sends back to draft──┘     │
                                             ▼
                                       [legal_pending]
                                            │
                                       approve│reject
                                            ▼     │
                                            └─sends back to reviewer─┐
                                                                     │
                                                                     ▼
                                                                [cfo_pending]
                                                                     │
                                                                approve│reject
                                                                     ▼     │
                                                                     └─sends back to legal─┐
                                                                                          │
                                                                                          ▼
                                                                                     [approved]
```

`approved` is the prerequisite for transitioning the parent notice to
`submitted` status. Once a response is `approved`, the notice's
`/api/compliance/notices/{id}/status` endpoint will accept the
`submitted` transition; before then it returns 409 Conflict.

**Reject transitions** record the reason in the approval row (immutable)
and revert the response to the previous stage's pending state — not back
to draft, except for reviewer rejection. This matches CA-firm practice
where Legal/CFO rejection means "send back one stage for rework."

---

## 3. Versioning model

Every PATCH on the response body creates a new `notice_response_versions`
row. The parent `notice_responses` row holds the `current_version_id` FK
+ `status`. Rollback writes a new version pointing at the older content
(monotonic versioning — never delete or amend a version row).

This mirrors v1.0's `document_versions` pattern from Phase 7.

---

## 4. Library versions (locked)

No new library deps for v2.0 — all data layer + state machine work uses
the existing SQLAlchemy + Pydantic + FastAPI stack. v2.1 adds:
- `pypdf` for evidence PDF merge
- `reportlab` for TOC generation

---

## 5. Open items deferred explicitly

| Item | Reason | v2.1 owner |
|------|--------|-----------|
| 20+ response templates | Lawyer/CA review cycle | Compliance content team |
| LLM draft generation | Prompt engineering + regression | Phase 5 LLM team |
| Evidence PDF merge | TOC design review | Frontend + backend joint |
| GST ITC reconciliation | CBIC schema instability | Backend + tax-domain expert |
| Regulation library | IP review on CBDT/CBIC PDFs | LegalOps |
| Per-client approval chain | Schema validation guardrails | v2.1 UI sprint |
| Approval-stage email alerts | Phase 11 dispatch + per-stage config | Phase 11 follow-up |

---

## 6. Open Blockers — RESOLVED

1. **Template authoring capacity**: out of scope for v2.0; v2.1 sprint.
2. **GSTR-2A/2B schema versioning**: out of scope for v2.0; revisit on
   next CBIC bulletin.
3. **Approval chain configuration**: hardcoded 4-stage chain in v2.0;
   per-client `config_overrides` in v2.1.
4. **Regulation library corpus**: out of scope for v2.0.
5. **PDF merge library choice**: defer to v2.1 alongside (3).

---

*Phase 12 research finalized 2026-05-05.*
