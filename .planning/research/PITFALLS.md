# Domain Pitfalls: Compliance Management on Existing DMS

**Domain:** Adding AI-powered compliance management to existing Indian regulatory document management system
**Researched:** 2026-03-30
**Confidence:** MEDIUM overall — architectural/ML patterns are HIGH confidence; Indian portal operational specifics are MEDIUM (training data cutoff August 2025; portal behaviors change frequently)

---

## Critical Pitfalls

Mistakes that cause rewrites, data loss, regulatory liability, or missed deadlines.

---

### Pitfall 1: Government Portal Session Expiry Causing Silent Retrieval Failures

**What goes wrong:** GST and IT portal sessions expire (typically 30–60 minutes for GST portal APIs, shorter for scraping sessions). When the background Celery/APScheduler job that fetches notices loses its session mid-run, it silently returns an empty result set — no error, no exception — and the system records "no new notices" rather than "retrieval failed." Notices that arrived during the gap are never fetched.

**Why it happens:** Portal authentication flows are stateful (cookie/session-based, not stateless JWT). Scheduled jobs that run every few hours do not refresh sessions proactively. Python's `requests.Session` does not automatically handle 302-redirect-to-login as an authentication failure — it follows the redirect and receives the login page as HTTP 200.

**Consequences:** Compliance notices silently missed. No alert fired. The deadline clock never starts. First indication is a missed hearing date or a demand order arriving after the response window closed. Regulatory penalties cannot be appealed on grounds of portal failure.

**Prevention:**
- Never treat an empty portal response as "no notices." Distinguish three states explicitly: `SUCCESS_EMPTY` (authenticated, no new notices), `SUCCESS_WITH_RESULTS`, and `FETCH_FAILED` (session expired, network error, HTTP 4xx/5xx).
- After every portal fetch, write a `PortalFetchLog` record with: timestamp, portal, entity_id, status, notices_found, error_detail. Alert via email/SMS to system admin if two consecutive `FETCH_FAILED` events occur for the same portal.
- Implement a session health-check before each fetch: call a lightweight authenticated endpoint (e.g., profile/taxpayer name API) and re-authenticate if it returns 401 or a redirect.
- Wrap all portal fetch functions in a decorator that detects redirect-to-login (check `Content-Type: text/html` on a JSON endpoint, or presence of login-form landmarks in response body) and raises `SessionExpiredException` — never returning an empty result.
- Store encrypted credentials in the database (not only env vars) so re-authentication can happen automatically inside Celery workers without manual operator intervention.

**Detection (warning signs):**
- Zero notices fetched for 3+ consecutive scheduled runs despite known activity on the portal
- HTTP 200 responses with `Content-Type: text/html` on endpoints that should return JSON
- Response body contains strings like "session expired", "login", "प्रवेश करें", or an HTML `<form>` element

**Phase assignment:** Portal Integration phase (fetch implementation). Fetch-status alerting in Alert System phase.

**Confidence:** HIGH — silent empty-result from expired session is the #1 operational failure mode in portal integration systems.

---

### Pitfall 2: Elasticsearch OOM Kills on Render Corrupting Indices

**What goes wrong:** Elasticsearch requires a minimum of 1 GB JVM heap (2–4 GB recommended for production). Render's standard instances (512 MB to 1 GB RAM) trigger OOM kills during indexing bursts. An OOM kill mid-translog-flush leaves index shards in an unrecoverable state requiring index deletion and full reindex from PostgreSQL.

**Why it happens:** ES heap is configured via `ES_JAVA_OPTS=-Xms1g -Xmx1g`. On a 1 GB instance, this allocation leaves zero memory for the OS, Docker overhead, and Elasticsearch's off-heap memory (file system cache, network buffers). Off-heap ES memory usage is routinely 50–100% of heap size again on top of the configured heap.

**Consequences:** Complete search outage. All notices become unsearchable. If PostgreSQL FTS fallback is not implemented, the entire compliance dashboard breaks. Worse: an OOM kill during bulk indexing corrupts 3 of 10 shards, and the system appears to work but silently returns incomplete results — the worst failure mode because it is invisible.

**Prevention:**
- On Render, use a dedicated service instance for Elasticsearch with at least 2 GB RAM (4 GB recommended). Do not colocate ES with the FastAPI application process.
- Set `ES_JAVA_OPTS=-Xms512m -Xmx512m` for development; `-Xms1g -Xmx1g` requires at minimum a 3 GB instance.
- Always implement PostgreSQL FTS as a fallback for search. ES is an enhancement, not a requirement for system operation. The compliance dashboard must remain fully functional when ES is down.
- Set `indices.breaker.total.limit: 70%` to trigger circuit breakers before OOM rather than letting ES crash.
- In Docker Compose, set `mem_limit: 2g` on the ES container to catch over-allocation in development before it reaches production.
- Strongly prefer a managed Elasticsearch service (Elastic Cloud free tier, Bonsai.io) for production over self-hosted on Render. This eliminates OOM management, shard recovery, index management, and upgrade complexity.

**Detection (warning signs):**
- Render logs show `Killed` or `OOMKilled` for the Elasticsearch container
- `GET /_cluster/health` returns `status: "red"`
- `GET /_cat/shards?v` shows shards in `UNASSIGNED` state

**Phase assignment:** Elasticsearch setup phase. Decision on managed vs. self-hosted must be made before any index design work begins.

**Confidence:** HIGH — Elasticsearch memory requirements are documented; Render resource constraints are a predictable integration challenge.

---

### Pitfall 3: BERT Classification Deployed to Production Without Calibration

**What goes wrong:** The team achieves 92%+ accuracy on a validation set, but production accuracy drops to 70–75% because: (a) training data was synthetic or drawn from public notices without capturing authority-specific format variations; (b) the model was evaluated on the same time-period distribution it was trained on (no temporal holdout); (c) new notice formats released post-training are misclassified with high confidence scores.

**Why it happens:** BERT fine-tuning requires 500–2,000+ examples per class for robust generalization. Indian compliance notices have extreme intra-class variance — an IT Section 148 notice and an IT Section 143(2) notice look structurally very different despite belonging to the same authority. BERT's softmax outputs are poorly calibrated by default: the model can output 94% confidence on an incorrect prediction.

**Consequences:** A SEBI LODR violation notice (15-day response window, up to ₹25L penalty) is misclassified as a routine GST notice. It is assigned to the Finance Team instead of Legal. No escalation is triggered. The response window expires. The penalty is levied. This is the highest-impact failure mode in the entire system.

**Prevention:**
- Do not deploy BERT for automatic routing or assignment until you have at least 300 real (not synthetic) labeled examples per class AND a held-out test set from a different time period than the training data.
- Implement temperature scaling or Platt scaling post-training to calibrate confidence scores. Raw softmax 94% is not 94% reliable.
- Set a low-confidence threshold (e.g., below 0.75 after calibration) that routes notices to a mandatory human review queue rather than auto-assigning to any team.
- Log all predictions with confidence scores and record ground truth once human-verified. Retrain monthly on accumulated real-world data.
- Implement two-stage classification: first classify authority (GST / IT / RBI / SEBI / Legal), then apply a second-stage classifier for notice type within that authority. Two smaller focused classifiers with limited data outperform one large multi-class classifier.
- Use IndoBERT or Legal-BERT (pre-trained on Indian legal text) as the base model rather than `bert-base-uncased`. Better initialization reduces data requirements for fine-tuning.

**Detection (warning signs):**
- Human review queue consistently overrides the auto-classifier output
- Notices from post-training regulatory changes are all classified as the most frequent class
- Confidence scores are uniformly above 0.9 regardless of notice content — a strong sign of miscalibration

**Phase assignment:** ML Classification phase. Temperature scaling calibration must happen before production deployment, not retrofitted later.

**Confidence:** HIGH — BERT calibration failure and domain shift are extensively documented ML engineering problems.

---

### Pitfall 4: Audit Trail Mutability Breaking Regulatory Inspection Readiness

**What goes wrong:** The compliance workflow (Received → Under Review → Response Drafted → Submitted → Resolved) involves multiple concurrent users. When Reviewer and Legal both modify a notice response simultaneously, optimistic locking without `SELECT FOR UPDATE` causes one user's change to silently overwrite the other's. More critically, audit log rows are written to PostgreSQL with application-generated timestamps — any database user with application credentials can UPDATE or DELETE rows, and this is undetectable.

**Why it happens:** Most audit implementations use application-level INSERT but do not enforce immutability at the database level. FastAPI endpoints that use `session.commit()` without explicit row locking are vulnerable to last-write-wins semantics. Application-generated `datetime.utcnow()` can be manipulated.

**Consequences:** During a regulatory inspection (IT scrutiny, SEBI investigation) or legal dispute, the compliance history is challenged as tampered. The company cannot prove when a notice was first received, when escalation occurred, or that it acted within the statutory response window. The audit trail — the core compliance value proposition — becomes legally worthless.

**Prevention:**
- Implement database-level immutability for audit logs: a PostgreSQL trigger that raises an exception on any `UPDATE` or `DELETE` against the `audit_log` table. This cannot be bypassed by application code.
- Use `GENERATED ALWAYS AS IDENTITY` for audit log IDs (prevents manual ID insertion) and `DEFAULT clock_timestamp()` for timestamps (prevents application-level forgery; `clock_timestamp()` is actual wall-clock time, unlike `now()` which is transaction start time).
- Apply optimistic locking via a `version` integer column: `UPDATE notices SET ... WHERE id=? AND version=?`. If 0 rows are updated, raise `ConcurrentModificationException`.
- Grant the application database user only `INSERT` on `audit_log`. Run `REVOKE UPDATE, DELETE ON audit_logs FROM app_user` explicitly.
- Implement hash chaining: each audit log row stores `hash = SHA256(previous_row_hash || this_row_content)`. Low-cost and provides cryptographic chain-of-custody evidence verifiable in any investigation.

**Detection (warning signs):**
- Two users both report "successfully saved" conflicting changes to the same response draft
- Audit log has timestamp gaps or non-monotonic auto-increment IDs
- Users report changes being overwritten shortly after saving

**Phase assignment:** Audit Trail phase. Database-level immutability must be implemented from day one — retrofitting requires data migration of existing logs.

**Confidence:** HIGH — database-level audit immutability is a standard requirement in compliance-grade systems.

---

### Pitfall 5: Compliance Notice PII Exposed in Logs, Redis Queue, and Elasticsearch

**What goes wrong:** HTTPS is implemented, PostgreSQL connections are encrypted, but notice content (PAN, GSTIN, CIN, DIN, financial figures, penalty amounts, legal section violations) appears in plaintext in: Celery task arguments stored in Redis, application log files captured by Render's log aggregation, Elasticsearch `_source` fields, and browser localStorage for response drafts.

**Why it happens:** "Encrypted at rest" is routinely misunderstood to mean disk encryption on the database server. It does not protect against a compromised application layer, insider access, or log aggregation. Python f-string logging is the most common PII leak vector: `logger.debug(f"Processing notice: {notice_dict}")` captures the entire deserialized notice object.

**Consequences:** A Redis compromise exposes all in-flight Celery task arguments including complete notice text with PAN and GSTIN data. Render's log retention captures notice content in plaintext for 30–90 days. This constitutes a personal data breach under the Digital Personal Data Protection Act 2023 (DPDP Act), triggering mandatory breach notification to the Data Protection Board of India within 72 hours. Regulatory fines up to ₹250 crore apply for systemic non-compliance.

**Prevention:**
- Implement field-level encryption for PII fields: PAN, GSTIN, CIN, DIN, bank account references. Use Fernet symmetric encryption (from `cryptography` library) with key from environment. Store encrypted bytes in `BYTEA` PostgreSQL columns with `_enc` suffix naming convention.
- Never log notice content. Log only notice IDs. Implement a structured logging filter that explicitly strips `notice_content`, `extracted_text`, `pan_number`, `gstin`, `amount` fields before any log output.
- Pass only notice `id` (not the notice object) to Celery task arguments. Workers fetch fresh data from the database inside the task context.
- Enforce Redis AUTH password and TLS in all environments. A development Redis without auth creates habits that propagate to production configurations.
- For Elasticsearch, restrict `_source` API access and use encrypted volumes. On Elastic Cloud this is on by default.
- Implement data retention policy: notices older than 7 years are archived to encrypted cold storage (regulatory retention requirement under IT Act) and removed from hot Elasticsearch indices.

**Detection (warning signs):**
- Application log files contain matches for GSTIN regex (`[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]`) or PAN regex (`[A-Z]{5}[0-9]{4}[A-Z]`)
- Redis queue inspection (`redis-cli LRANGE celery 0 5`) shows full notice text in task arguments
- Elasticsearch `_source` API returns unredacted PAN or GSTIN in search results

**Phase assignment:** Security phase. Must precede any portal integration. Field-level encryption is expensive to retrofit after data is already stored in plaintext.

**Confidence:** HIGH — Indian financial data sensitivity requirements are well-established; DPDP Act 2023 is in force.

---

## Moderate Pitfalls

### Pitfall 6: Indian Regulatory Deadline Calculation Without Holiday Calendar

**What goes wrong:** The system calculates deadlines as `notice_date + timedelta(days=N)`. This produces incorrect deadlines because: GST response deadlines shift when the due date falls on a Sunday or declared public holiday (extended to next working day); Indian public holidays are not uniform across states (Maharashtra and Karnataka gazetted holidays differ); CBDT and CBIC issue circulars extending deadlines during elections, system outages, and other events; GST, Income Tax, and Companies Act deadlines follow different holiday rules.

**Why it happens:** `datetime + timedelta(days=N)` is naive. India has 26 central government holidays per year plus state-specific gazetted holidays. No standard Python library includes Indian regulatory holiday calendars. Circular-based extensions are issued ad hoc and cannot be computed programmatically.

**Consequences:** The system shows a deadline of Sunday, March 30. The user assumes they have until Monday, March 31. The CBIC issued a circular extending to Tuesday, April 1. The system knows nothing about the circular. The user submits Monday evening, misses the actual Tuesday-extended deadline, and is assessed a late fee of ₹200/day (GST regime). The opposite failure also occurs: system shows an extended deadline that was not actually granted for that specific notice type, giving false comfort.

**Prevention:**
- Build a `RegulatoryCalendar` table: authority, year, holiday_date, holiday_name, state (null = national), source_url. Pre-populate from CBDT, CBIC, and state government official holiday notifications for the current year.
- Deadline calculation must use: `next_working_day(base_date + timedelta(days=N), authority=authority, state=state)`. Never use raw timedelta in the deadline calculation layer.
- Add a `DeadlineExtension` table: authority, notice_type, original_deadline, extended_deadline, circular_reference, circular_url. Admin UI for the compliance team to update when new circulars are issued.
- Store all datetimes in UTC in the database. Display as IST (UTC+5:30) in the UI. Use `zoneinfo` with `Asia/Kolkata`. Never store naive (timezone-unaware) datetimes.
- Display a persistent disclaimer on all deadline fields: "Verify on official portal — deadline may be extended by circular." Until the circular database is confirmed current for the current period.

**Detection (warning signs):**
- Deadline values in the UI consistently fall on Sundays without any weekend adjustment
- Users report discrepancies between system deadlines and portal deadlines
- The `RegulatoryCalendar` table is empty or has no entries for the current year

**Phase assignment:** Compliance Tracking / Dashboard phase.

**Confidence:** HIGH — India-specific statutory deadline calculation complexity is well-established tax practice knowledge.

---

### Pitfall 7: Notification Fatigue from Undifferentiated Alert Volume

**What goes wrong:** The system sends T-7, T-3, and T-1 reminders for all notices regardless of risk level or current status. A Compliance Head managing 50 active notices receives 150 reminder emails per week. They begin ignoring all system emails. A genuine T-1 alert for a ₹25L SEBI penalty notice — sent as one of 30 emails that day — is not seen before the deadline closes.

**Why it happens:** Alert systems are built feature-complete (all reminders active by default) during development. "Alert on everything" is the safe default during implementation. Users do not configure preferences until they are already fatigued. The system that was designed to prevent missed deadlines begins contributing to them.

**Consequences:** Users disable email notifications entirely. Critical notices go unresponded. Compliance officers argue that the system "cried wolf" and the real alert was lost in noise. This is a documented pattern in security monitoring (SIEM alert fatigue) and applies equally to compliance alerting.

**Prevention:**
- Define alert priority tiers from the first day of implementation: CRITICAL (penalty above ₹10L, government hearing scheduled, court summons — all channels, every T-N reminder), HIGH (penalty ₹1L–10L — email at T-3 and T-1 only), MEDIUM (routine compliance — email at T-7 and T-1 only), LOW (informational — in-app only, no email or SMS).
- Default configuration must be conservative: only CRITICAL and HIGH notices send email or SMS. Users must opt in to broader alert coverage.
- Batch all LOW and MEDIUM in-app alerts into a single daily digest email. Send at a fixed time (9 AM IST) rather than individually.
- Implement acknowledgment-based suppression: once a user opens and acknowledges a notice, suppress further T-N reminders for that notice unless the deadline changes or status reverts to unreviewed.
- Enforce a minimum 24-hour gap between alerts for the same notice unless status changes.

**Detection (warning signs):**
- Email open rate for compliance alert emails drops below 30%
- Users have disabled email notifications in account preferences
- System sends more than 10 alert emails per user per day

**Phase assignment:** Alert System phase. Priority tiers must be designed before implementation begins.

**Confidence:** HIGH — notification fatigue is a universally documented anti-pattern in monitoring, compliance, and security alerting systems.

---

### Pitfall 8: CAPTCHA and Data Center IP Blocking Scraping RBI/SEBI Portals Without Detection

**What goes wrong:** RBI and SEBI notices are retrieved via web scraping (no official API). After 50–100 requests per session, or when requests originate from data center IP ranges (Render runs on AWS infrastructure), the portal serves a CAPTCHA challenge page or silently returns an empty response body. The scraper receives HTTP 200, treats the response as "no new notices," and reports success.

**Why it happens:** Web scrapers do not distinguish between "authenticated empty result page" and "CAPTCHA/bot-blocking page" unless explicitly coded to detect the difference. Government portals increasingly flag requests from cloud provider IP CIDR blocks as automated traffic. AWS IP ranges are public and widely used in bot-blocking lists.

**Consequences:** RBI or SEBI scraping silently fails for days or weeks. New regulatory circulars, Master Directions, or show-cause notices are not ingested. The compliance team operates on the assumption that coverage is current when the retrieval pipeline has been broken since the last AWS IP rotation.

**Prevention:**
- Validate every scraped page response for expected structural landmarks before parsing. If the expected notice-listing container element is absent (e.g., `<table class="notice-list">` or equivalent), raise `ScrapingBlockedException` — never return an empty result.
- Implement HTML fingerprint checks: each scraping function has an assertion about the minimum expected content structure. Absence triggers a `FETCH_FAILED` log and admin alert, not a silent empty return.
- Document IP rotation or residential proxy as a known operational requirement if data center IP blocking becomes persistent. Plan for this before it becomes an incident.
- For RBI and SEBI, designate email forwarding and manual upload as the primary notice intake channels. Treat scraping as supplementary. This reduces operational fragility and regulatory risk.
- Alert system administrators if any portal scraper returns zero results for more than 48 consecutive business hours. Government portal notice boards are not legitimately empty for two full business days.

**Detection (warning signs):**
- Scraper logs show HTTP 200 but response body contains words like "captcha", "verify", "automated", or "robot"
- Scraped result count drops to exactly zero across multiple consecutive business days
- Response HTML payload size is substantially smaller than a legitimate notice listing page (login or CAPTCHA pages are typically 5–20KB; notice listing pages are 50–200KB)

**Phase assignment:** Portal Integration phase. Defensive scraping structure must be designed before implementation.

**Confidence:** MEDIUM — specific current behavior of RBI/SEBI portals regarding bot detection should be verified empirically before implementation.

---

### Pitfall 9: NER Extraction Fails on Indian-Specific Legal and Regulatory Formats

**What goes wrong:** spaCy's pre-trained English NER models (`en_core_web_sm`, `en_core_web_lg`) do not recognize Indian regulatory entity formats: GSTIN (15-character alphanumeric with embedded state code), PAN (10-character fixed format ABCDE1234F), CIN (21-character company identifier), DIN (8-digit director identification number), section references such as "u/s 143(2) of the Income Tax Act, 1961" or "Section 16(4) of the CGST Act, 2017", and Indian court identifiers (CS/1234/2024, W.P. No. 5678/2025). These are silently missed or incorrectly labeled as generic NUMBER or ORG entities.

**Why it happens:** spaCy's English models were trained primarily on news and web text. Indian regulatory documents use a highly specific vocabulary: "impugned order," "ex-parte," "inter alia," "sub-judice," "quantum of demand," "adjudicating authority," authority abbreviations (AO, PCIT, DCIT, ADIT, CIT(A), ITAT), and Indian number formatting where ₹15,00,000 is fifteen lakh (not 1.5 million, which breaks amount extraction).

**Consequences:** NER extraction returns null or incorrect values for notice number, deadline, and penalty amount. Downstream XGBoost risk scoring receives null feature values. A ₹25L SEBI notice is scored as low-risk because `penalty_amount` is null. No escalation is triggered. The notice misses its response window.

**Prevention:**
- Do not rely on spaCy pre-trained NER for Indian-specific structured entities. Implement regex-based extractors as the primary extraction method for all structured entities:
  - GSTIN: `[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]`
  - PAN: `\b[A-Z]{5}[0-9]{4}[A-Z]\b`
  - CIN: `[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}`
  - DIN: contextually anchored `\b[0-9]{8}\b` (require "DIN" within 50 characters)
  - Section references: `(u/s|under [Ss]ection|[Ss]ection)\s+[\d()\w/]+`
  - Indian currency: `₹\s*[\d,]+(\s*(lakh|crore|thousand|Lakh|Crore))?` with normalization to absolute rupee values
- Reserve spaCy NER fine-tuning for genuinely ambiguous entities where regex is insufficient (officer names, authority names in unstructured prose).
- When XGBoost risk scoring receives null values for `penalty_amount` or `deadline_days`, default the risk output to HIGH. Never let missing features produce a low-risk score. Fail safe, not fail open.
- Validate extraction against real notice samples from all six authority categories before deployment.

**Detection (warning signs):**
- More than 30% of ingested notices have null `deadline` or null `penalty_amount` fields
- GSTIN extraction field contains non-GSTIN strings or is blank on notices that visibly contain a GSTIN
- Risk scores cluster at the low end despite the presence of known high-value notices

**Phase assignment:** NER/Extraction phase. Regex-first architecture must be decided in design before implementation begins.

**Confidence:** HIGH — spaCy's limitations with Indian regulatory text follow directly from its documented English news training corpus.

---

### Pitfall 10: Elasticsearch Index Drift from PostgreSQL Source of Truth

**What goes wrong:** A notice is created in PostgreSQL. A Celery task attempts to index it to Elasticsearch. The task fails silently due to a transient Redis connection timeout or an Elasticsearch restart. The notice exists in PostgreSQL but is absent from Elasticsearch. Searches miss it entirely. A more damaging version: a notice status is updated to "Resolved" in PostgreSQL but the ES update task fails. The search index continues showing the notice as "Pending" indefinitely.

**Why it happens:** Dual-write architectures (write to DB then write to ES) have a fundamental failure mode: the second write can fail while the first succeeds. Without a reconciliation mechanism, the indices drift over time in a way that is invisible until a user searches for a notice they know exists and cannot find it.

**Consequences:** Notices invisible to compliance dashboard search. Auditor queries return incomplete result sets. Users lose confidence in the system and stop using search, defaulting to manual list scrolling. Resolved notices appearing as pending in search create incorrect compliance status reports.

**Prevention:**
- Use the transactional outbox pattern: write to a `search_index_queue` PostgreSQL table atomically within the same database transaction as the notice write. A separate Celery task polls this outbox, indexes to ES, and marks rows as processed on success. Retry failed rows with exponential backoff.
- Run a reconciliation Celery beat job daily: compare PostgreSQL notice count with ES document count per index. Log discrepancy. Alert if drift exceeds 1%.
- ES is eventually consistent and non-authoritative. All business logic reads (status, deadline, assignment, risk score) must come from PostgreSQL. ES handles only full-text search queries.
- Add `es_indexed_at` timestamp to the PostgreSQL notices table. Rows where `es_indexed_at IS NULL OR es_indexed_at < updated_at - interval '10 minutes'` are queued for re-indexing by the reconciliation job.

**Detection (warning signs):**
- PostgreSQL `SELECT COUNT(*)` and Elasticsearch `_count` diverge by more than 1%
- A notice found via PostgreSQL-backed filters cannot be found via full-text search
- Status displayed in search results differs from status displayed in the notice detail view

**Phase assignment:** Elasticsearch Integration phase.

**Confidence:** HIGH — dual-write consistency failure is a well-documented distributed systems problem with established solutions.

---

### Pitfall 11: v1.0 Document Management Performance Degraded by v2.0 ML Components

**What goes wrong:** Adding Elasticsearch, BERT inference, XGBoost scoring, WebSocket connections, and APScheduler compliance jobs to the same Render service instance causes: (a) memory pressure that increases v1.0 document upload response times from 200ms to 2–3 seconds; (b) APScheduler periodic compliance fetch jobs competing with Celery workers that serve v1.0 document processing queues; (c) BERT model loading on every deployment adding 15–20 seconds to cold start time and triggering Render's health check timeout, causing restart loops.

**Why it happens:** `bert-base-uncased` is 440 MB and requires 10–15 seconds to load on first inference. Running BERT model loading in the FastAPI startup lifecycle means every deployment causes a cold start penalty. Adding ML and scheduling components without resource isolation degrades all existing services.

**Consequences:** v1.0 API response SLA (below 500ms) is violated for existing users who do not use compliance features. Health check failures trigger Render restart loops, causing repeated downtime. The v2.0 rollout breaks existing working functionality.

**Prevention:**
- Load BERT and XGBoost models once using a module-level singleton. Never load models per-request. Pattern: `_bert_model = None; def get_bert_model(): global _bert_model; if _bert_model is None: _bert_model = load_model(); return _bert_model`
- Move BERT inference to a dedicated Celery worker queue (`-Q ml_inference`) running in a separate process. Never run BERT inference synchronously in the request-response path.
- Run APScheduler compliance fetch jobs as Celery beat scheduled tasks, not inside FastAPI application startup. The existing Celery beat process already handles this.
- Add performance regression tests to CI: measure p95 latency for core v1.0 endpoints (document upload, search, classification) before and after v2.0 code additions. Fail the build if v1.0 p95 degrades by more than 20%.
- Monitor v1.0 and v2.0 endpoint latency separately in production with explicit alerts.

**Detection (warning signs):**
- v1.0 document upload or search endpoint response times increase measurably after any v2.0 deployment
- Render deployment logs show health check failures or restart loops on first startup after adding BERT
- Celery `document_processing` queue depth grows after APScheduler compliance jobs start consuming worker capacity

**Phase assignment:** Integration Architecture phase — resource isolation strategy must be decided before v2.0 ML components are added to the service. Retrofit is disruptive.

**Confidence:** HIGH — ML model cold start penalties and Celery queue resource contention are predictable and well-documented engineering problems.

---

### Pitfall 12: Regulatory Law Changes Cause Concept Drift Without Detection Mechanism

**What goes wrong:** GST law is amended (new ITC reversal rules under Rule 86B, revised GSTR-9C requirements, new Section 74A notices). Authorities issue notice types the BERT classifier has never seen in training. The classifier confidently misclassifies them as the nearest known class. No mechanism detects "unknown notice type encountered." Simultaneously, the compliance library regulation repository becomes stale as CBDT circulars, RBI Master Directions, and SEBI LODR amendments accumulate without being captured.

**Why it happens:** ML classifiers are closed-world systems — they can only predict classes they were trained on. A BERT classifier trained in February will never output "Section 74A Notice" if that notice type was introduced by a March amendment. Regulatory changes in India are frequent: CBDT issues 30–50 circulars per year, CBIC issues 20–40, and RBI issues continuous Master Direction updates.

**Consequences:** New notice types are misclassified with high confidence. Wrong team assignment. Wrong response template applied. Regulation library references superseded text. A legal response based on an old circular is filed. This is a recurring, escalating problem without an active mitigation.

**Prevention:**
- Implement out-of-distribution (OOD) detection using classification entropy: high entropy across predicted class probabilities (near-uniform distribution) indicates the model does not recognize the notice type. Route these to a human review queue, not to any team.
- Add an `UNKNOWN_TYPE` as a valid classification output. Train the model on a diverse "miscellaneous" class so it has an explicit reject option rather than being forced to choose between known classes.
- Version regulation library entries: each record has `effective_from` (date), `effective_to` (nullable, null means currently effective), and `superseded_by` (FK to new record). Never delete historical regulation records.
- Subscribe to CBDT, CBIC, RBI, and SEBI official notification feeds. When a new circular is detected, create a task in the compliance team's workflow to review and update the regulation library.
- Define a quantitative retraining trigger: if more than 5% of notices in a calendar month land in the human review queue, schedule BERT retraining with newly accumulated labeled data.

**Detection (warning signs):**
- Human review queue volume grows month-over-month without a corresponding increase in total notice volume
- Classification confidence drops for a specific authority following a known regulatory change date
- Regulation library has no entries with `effective_from` in the last 6 months for an active regulatory domain

**Phase assignment:** ML Classification phase (OOD detection mechanism) and Regulatory Library phase (versioned regulation records). Both must be designed before respective implementations.

**Confidence:** HIGH — concept drift in production ML systems is an extensively documented operational problem. Indian regulatory change frequency amplifies this risk specifically.

---

## Minor Pitfalls

### Pitfall 13: CI/CD Tests Calling Live Government Portal APIs

**What goes wrong:** Integration tests call live GST or IT portal APIs. The portal experiences downtime during a CI run. All integration tests fail. The developer assumes their code change is the cause and spends hours debugging. Alternatively, tests pass because the portal returns stale or cached data that does not match the test's expected fixture, producing false confidence.

**Prevention:**
- Never call live government portal APIs in automated tests. Create `PortalClientStub` classes implementing the same interface as real portal clients and returning fixture data from files. Use FastAPI dependency injection to swap stubs in tests.
- Record real portal responses (with PII fully removed from fixtures) as VCR cassettes using `pytest-recording` or the `responses` library. Tests replay pre-recorded HTTP interactions deterministically.
- Live portal tests exist only in `tests/integration/live/`, run manually with `pytest -m live_portal`, and are never included in the CI pipeline.

**Phase assignment:** Portal Integration phase. Test strategy must be established before implementation begins.

**Confidence:** HIGH.

---

### Pitfall 14: Multi-GSTIN Data Isolation Failure in Shared CA Dashboard

**What goes wrong:** A Chartered Accountant user has access to 5 client GSTINs. A query to the compliance dashboard for "all pending notices" returns notices from all 5 clients because the SQLAlchemy query lacks entity-scoping. Notice data from Client A is visible to Client B's internal team members.

**Prevention:**
- Every compliance-related database query must include `WHERE entity_id IN (SELECT entity_id FROM user_entity_access WHERE user_id = ?)` or equivalent filter. Enforce this at the SQLAlchemy repository layer, not at the API route layer. Repository-layer enforcement cannot be bypassed by a new route added later.
- Write a mandatory integration test: create two entities, create notices for each, authenticate as a user with access to entity 1 only, assert no entity 2 notices appear from any endpoint.

**Phase assignment:** RBAC / Client Management phase.

**Confidence:** HIGH.

---

### Pitfall 15: WebSocket Silent Disconnect at Load Balancer Idle Timeout

**What goes wrong:** Render's load balancer enforces an idle connection timeout. WebSocket connections that are idle (no new notice events) are silently closed by the load balancer without sending a WebSocket close frame. The frontend JavaScript WebSocket client remains in the `OPEN` state according to its own state machine. Users see a green "connected" indicator but receive no notifications until they reload the page.

**Prevention:**
- Implement WebSocket application-level heartbeat: server sends a `ping` message every 30 seconds; client responds with `pong`. If no pong is received within 10 seconds, the server closes the connection; the client detects the close event and reconnects.
- Client-side reconnection with exponential backoff: 1s, 2s, 4s, 8s, max 30s.
- Display an explicit connection status indicator in the UI. Users must always be able to see whether live updates are active. Never rely on the connection being silently live.

**Phase assignment:** WebSocket / Notification phase.

**Confidence:** MEDIUM — specific Render load balancer idle timeout value should be verified in current Render documentation before finalizing the heartbeat interval.

---

### Pitfall 16: Concurrent Portal Fetch Jobs Creating Duplicate Notices

**What goes wrong:** APScheduler fires a portal fetch job every 2 hours. When the Render service restarts (due to deployment, OOM kill, or health check failure), APScheduler starts a new fetch job immediately on restart. The previous job is still running in Celery. Both jobs fetch the same portal, find the same new notice, and both successfully create database records — resulting in duplicate notices, duplicate deadline calculations, and duplicate alerts to users.

**Prevention:**
- Define a unique constraint in PostgreSQL: `UNIQUE (notice_number, authority, entity_id)`. Duplicate insert attempts fail at the database level regardless of application code.
- Use `INSERT INTO notices (...) ON CONFLICT (notice_number, authority, entity_id) DO NOTHING` as the notice creation statement.
- Acquire a Redis distributed lock (`redis-py Lock`) per `{authority}:{entity_id}` key at the start of each Celery fetch task. Only one concurrent fetch task can hold the lock per authority per entity.

**Phase assignment:** Portal Integration / Scheduling phase.

**Confidence:** HIGH.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|----------------|------------|
| Portal Integration (GST/IT/MCA) | Session expiry returns empty result, no error | Explicit `FETCH_FAILED` / `SUCCESS_EMPTY` distinction; `PortalFetchLog` on every run |
| Portal Integration (RBI/SEBI scraping) | AWS/Render IPs blocked; CAPTCHA served as HTTP 200 | HTML structure validation; admin alert for zero-result streaks over 48 business hours |
| BERT Classification | Miscalibrated confidence scores; domain shift | 300+ real examples per class; temperature scaling before production; two-stage classifier |
| NER Extraction | spaCy misses GSTIN/PAN/CIN/section references | Regex-first for all structured Indian entities; null penalty defaults to HIGH risk |
| Elasticsearch Setup | OOM kills corrupt shards; no PostgreSQL fallback | Managed ES service strongly preferred; PostgreSQL FTS fallback mandatory for all queries |
| ES Index Consistency | Dual-write failure causes search/DB divergence | Transactional outbox pattern; daily reconciliation job |
| XGBoost Risk Scoring | Null NER features produce erroneously low risk scores | Any null penalty_amount or deadline input maps to HIGH risk output |
| Alert System | Reminder volume causes users to ignore all alerts | CRITICAL/HIGH/MEDIUM/LOW tiers from day one; daily digest; acknowledgment-based suppression |
| Compliance Tracking | Raw timedelta ignores Indian holidays and circulars | `RegulatoryCalendar` table; `DeadlineExtension` table for ad hoc circular extensions |
| Audit Trail | Application-layer timestamps are mutable | DB-level INSERT-only trigger; `REVOKE UPDATE DELETE`; hash chain; `clock_timestamp()` |
| Data Security | PII in application logs, Redis args, Elasticsearch | Field-level Fernet encryption; ID-only Celery args; structured log field blocklist |
| v1.0 Performance Integration | BERT cold start degrades existing endpoint SLAs | Module-level model singleton; dedicated `ml_inference` Celery queue; p95 regression tests in CI |
| Regulatory Library | Post-training notice types misclassified confidently | Entropy-based OOD detection; `UNKNOWN_TYPE` class; versioned `effective_from/to` regulation records |
| RBAC / Multi-client CA | Cross-entity notice leakage in shared queries | Repository-layer entity scoping enforced, not route-layer; mandatory isolation integration test |
| WebSocket Notifications | Silent LB disconnect; client believes connection is live | 30-second heartbeat; client auto-reconnect with backoff; visible connection status indicator |
| CI/CD Pipeline | Live portal calls make tests flaky and environment-dependent | `PortalClientStub` via DI; VCR cassettes; `live_portal` marked tests manual-only, never in CI |
| Scheduling / APScheduler | Service restart fires duplicate fetch jobs | `UNIQUE (notice_number, authority, entity_id)` constraint; Redis distributed lock per task |

---

## Sources

Primary source: Training data knowledge (cutoff August 2025). No live web search was available during this research session.

**HIGH confidence findings** — based on documented, stable technical behaviors:
- Elasticsearch JVM heap and OOM behavior (official ES documentation)
- BERT calibration failure and domain shift (NeurIPS/ICML published literature)
- PostgreSQL audit immutability with triggers and row-level security
- Celery dual-write consistency and transactional outbox pattern
- Indian statutory deadline rules (GST Act, Income Tax Act holiday provisions)
- spaCy NER training corpus scope (spaCy documentation and model cards)
- Notification fatigue in monitoring/compliance systems (documented UX anti-pattern)
- WebSocket heartbeat requirements for stateful load balancer persistence

**MEDIUM confidence findings** — Indian portal operational specifics, may have changed since August 2025:
- GST portal session timeout duration (30–60 minutes estimate; verify empirically)
- Render load balancer idle timeout value (verify in current Render documentation)
- RBI and SEBI portal bot detection behavior (verify current scraping feasibility before building)
- GST portal sandbox environment availability and API stability

**Required verification actions before Phase 1 implementation:**
1. Authenticate to GST portal manually and measure actual session timeout duration
2. Verify Render service tier memory limits for the compliance service instance to size Elasticsearch appropriately
3. Confirm whether GST portal sandbox/test environment is accessible for integration testing
4. Obtain current-year CBDT, CBIC, and relevant state holiday lists for the `RegulatoryCalendar` table seed data
5. Verify Render load balancer idle timeout in current Render documentation to set the correct WebSocket heartbeat interval
6. Assess feasibility of RBI and SEBI portal scraping from a Render-hosted IP before building the scraping pipeline
