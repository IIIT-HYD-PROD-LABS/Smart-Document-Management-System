# TaxSync Notice Ingest Pipeline + Gov Portal Roadmap

> **For Hermes:** Use subagent-driven-development for later portal phases.
> **Date:** 2026-07-16

**Goal:** Make every notice source (email, Drive, manual upload, future portals) land in client compliance automatically after document intelligence, with calendar / audit / reports reflecting the same data.

**Architecture:** One **Ingest → Intelligence → Compliance → Surfaces** pipeline. Portals are additional *sources* that emit the same internal events; they are not a separate product.

**Tech stack:** FastAPI, Celery, Tesseract OCR, pdfplumber, sklearn classifier, Phase 17 LLM/regex extraction, Postgres RLS, Next.js dashboard.

---

## Current reality (what already works)

```
Gmail / Drive / Manual PDF
        │
        ▼
  Document row (storage)
        │
        ▼
  process_document_task
    • Tesseract / pdfplumber text
    • category classify (document intelligence)
    • LLM/regex metadata
        │
        ▼
  ComplianceNotice (email/filter/AI routes)
    • extract fields → fill columns
    • process_notice_intake
        • classify_and_score_notice (risk)
        • schedule_deadline_alerts (T-7/T-3/T-1)
        │
        ├── Dashboard notices list
        ├── Calendar (statutory + notice deadlines overlay)
        ├── Audit log (NOTICE_AUTO_CREATED / status changes)
        └── Reports (health summary, volume, penalty, response time)
```

**Important:** Unofficial scraping of GSTN / Income Tax e-filing portals is **not** a safe production path (legal + CAPTCHA + TOS). The product path is:

1. **Email-first** (gov domains already email notices) — ship now  
2. **Portal export upload** (user downloads PDF from portal → TaxSync) — ship now  
3. **Licensed GSP / official APIs** when available — later  

---

## Target pipeline (single contract)

Every source must produce:

| Stage | Owner | Output |
|---|---|---|
| 1. Ingest | email / drive / upload / portal adapter | `Document` + raw bytes |
| 2. Intelligence | `process_document_task` | `extracted_text`, category, confidence, AI fields |
| 3. Route | classifier / filter rules / human | `compliance_notice` \| `bill` \| `dms_only` |
| 4. Notice | notice create + Phase 17 extract | `ComplianceNotice` columns filled |
| 5. Intake | `process_notice_intake` | risk score + alerts |
| 6. Surfaces | APIs already mounted | dashboard, calendar, audit, reports |

---

## Phased plan

### Phase A — Harden email → OCR → compliance (NOW)

1. After OCR on an attachment linked to a notice, **re-run** extraction fill + `process_notice_intake` so deadlines from PDF hit calendar alerts.  
2. Prefer attachment text over empty email body for Phase 17 extract.  
3. Ensure audit actions are visible for compliance_head / CA.  
4. Document operators: Scan now → wait Celery → open Compliance / Calendar.

### Phase B — Portal export channel (NEXT)

1. UI: “Import from portal export” on upload/notice new (reuse Drive + manual).  
2. `Document.source = portal`, `ComplianceNotice.source = portal`.  
3. Optional portal label metadata (`gst_portal`, `it_efiling`, `mca`).  
4. Same OCR → extract → intake chain as email.

### Phase C — Connector framework (LATER)

1. Abstract `PortalConnector` interface: `list_notices()`, `download(id) → bytes`.  
2. First connector: **manual folder watcher / SFTP drop** (no CAPTCHA).  
3. Second: **licensed GSP API** if team obtains credentials.  
4. Never ship headless login scrapers against gov sites in main product.

### Phase D — Surfaces polish

1. Dashboard “Pipeline health” card: last Gmail scan, pending OCR, open notices.  
2. Calendar seed FY for missing years.  
3. Report CSV exports already exist — ensure role matrix allows heads/CAs.

---

## File map (implementation)

| Area | Path |
|---|---|
| Email route + notice create | `backend/app/email/services/ingestion_service.py` |
| OCR + classify | `backend/app/tasks/document_tasks.py`, `backend/app/ml/*` |
| Notice intake | `backend/app/compliance/services/notice_service.py` |
| Risk ML | `backend/app/tasks/compliance_tasks.py` |
| Calendar | `backend/app/compliance/routers/calendar.py` + frontend calendar page |
| Audit | `backend/app/compliance/routers/audit.py` |
| Reports | `backend/app/compliance/routers/reports.py` |
| Pipeline orchestration helper | `backend/app/compliance/services/notice_pipeline.py` (new) |

---

## Acceptance tests

1. PDF-only Gmail notice (empty body) → after OCR, notice has deadline + appears on calendar month.  
2. Manual upload on notice → fields fill → intake risk score set.  
3. Audit shows `NOTICE_AUTO_CREATED` for compliance_head.  
4. Reports health-summary returns 200 for client with notices.  
5. CI green (ephemeral Postgres — not campus network).

---

## Risks

| Risk | Mitigation |
|---|---|
| Gov portal scraping blocked / illegal | Email + export + GSP only |
| Empty email body | OCR attachment then re-extract |
| Celery down | scan-now still creates notice; intake retries via cron |
| Calendar empty | statutory seed + notice deadline overlay |

---

## Immediate code tasks (this session)

1. `notice_pipeline.after_document_intelligence(document_id)` — re-extract + re-intake  
2. Call it from `process_document_task` after Phase 17  
3. Unit tests for pipeline helper  
4. Operator doc in `docs/operations/NOTICE_PIPELINE.md`
