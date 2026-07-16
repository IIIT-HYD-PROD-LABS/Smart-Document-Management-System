# Notice pipeline (email → OCR → compliance → calendar / audit / reports)

## Operator path (today)

1. **Connect Gmail** (Email → Connect) for the active organization.  
2. Click **Scan now** (or wait for cadence).  
3. Celery worker runs:
   - attachment save → `process_document_task` (Tesseract / pdfplumber + classify)
   - route → `ComplianceNotice` create
   - after OCR: field extract + `process_notice_intake` (risk + alerts)
4. Open **Compliance → Notices** — new rows appear with source `gmail`.  
5. **Calendar** — statutory deadlines + notice `response_deadline` chips.  
6. **Audit log** — `NOTICE_AUTO_CREATED` (compliance_head / auditor / CA).  
7. **Reports** — health summary / volume / penalty for the client.

## Why PDF-only emails now work

Gov mail often has an empty body and a PDF attachment. The pipeline:

1. Creates a notice immediately (from sender/subject rules).  
2. OCR’s the PDF.  
3. Re-fills notice columns from OCR text.  
4. Re-dispatches risk scoring + deadline alerts.

Code: `app/compliance/services/notice_pipeline.py` called from
`process_document_task`.

## Portal / GST portal strategy

Do **not** scrape GSTN or Income Tax portals without a licensed channel.

| Phase | Approach |
|---|---|
| Now | Email from `@*.gov.in` + Drive + manual upload |
| Next | “Portal export” upload (`source=portal`) same pipeline |
| Later | Licensed GSP / official APIs behind a connector interface |

Roadmap: `.hermes/plans/2026-07-16_145400-notice-pipeline-portal-roadmap.md`

## Celery must be running

```bash
docker compose up -d redis celery_worker compliance_worker backend
# or campus:
docker compose -f docker-compose.prod.yml up -d
```

Without workers, files and notices can still be created, but OCR / risk / alerts wait until a worker is up.

## Health checks

```bash
curl -s http://127.0.0.1:8025/api/health/live
# campus:
curl -s https://canvas.iiit.ac.in/taxsyncbestage/api/health/live
```
