---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: active
stopped_at: Completed 05-03-PLAN.md -- LLM settings API and settings page
last_updated: "2026-03-17"
last_activity: "2026-03-17 -- Phase 5 plan 03 complete (settings API + UI)"
progress:
  total_phases: 8
  completed_phases: 4
  total_plans: 16
  completed_plans: 16
  percent: 55
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-17)

**Core value:** Automated classification and intelligent organization of personal and business documents -- upload any document and the system automatically identifies its type, extracts key data, and makes it instantly searchable.
**Current focus:** Phase 5 Smart Extraction (AI) -- plan 03 complete (settings API + UI), next: 05-04 (extraction endpoint)

## Current Position

Phase: 5 of 8 (Smart Extraction AI) -- In progress
Plan: 3 of 4 in current phase
Status: Plan 05-03 complete. Settings API (GET/PUT) with encrypted key storage and 4-provider settings page.
Last activity: 2026-03-17 -- Completed 05-03-PLAN.md (settings API + settings page)

Progress: [████████████████░░░░░░░░░░░░░] 16/29 (55%)

## Performance Metrics

**Velocity:**
- Total plans completed: 16
- Average duration: ~8min
- Total execution time: ~122min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation-security-hardening | 4/4 | 41min | 10min |
| 02-document-processing-pipeline | 4/4 | ~24min | ~6min |
| 03-ml-classification-upgrade | 2/2 | 19min | ~10min |
| 04-search-retrieval | 3/3 | ~28min | ~9min |
| 05-smart-extraction-ai | 3/4 | 10min | ~3min |

**Recent Trend:**
- Last 5 plans: 04-02 (8min), 04-03 (5min), 05-01 (4min), 05-02 (2min), 05-03 (4min)
- Trend: Fast execution continues; full-stack plans (backend+frontend) still under 5min

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: 8-phase structure derived from 42 requirements across 8 categories
- [Roadmap]: Security hardening first (Phase 1) before any feature work
- [Roadmap]: Celery async wiring grouped with document processing (Phase 2), not infrastructure
- [01-01]: SECRET_KEY and DATABASE_URL have no defaults -- app crashes on startup if missing
- [01-01]: SECRET_KEY validator rejects 4 known-insecure values and keys <32 chars
- [01-01]: ACCESS_TOKEN_EXPIRE_MINUTES default reduced from 1440 to 30 minutes
- [01-01]: CORS restricted to explicit origins from ALLOWED_ORIGINS env var
- [01-01]: Rate limiter module created early for Wave 2 plans to import
- [01-02]: Opaque refresh tokens (not JWT) for server-side revocability
- [01-02]: Token rotation on every refresh; reuse detection revokes ALL user tokens
- [01-02]: Queue pattern in frontend prevents concurrent refresh requests
- [01-02]: sameSite: "Strict" on all auth cookies for CSRF protection
- [01-03]: HSTS max-age 2 years with preload, only in production (DEBUG=False)
- [01-03]: CSP unsafe-inline for style-src only; scripts remain strict 'self'
- [01-03]: Middleware order: CORS > SecurityHeaders > RequestLogging > CorrelationId
- [01-03]: Swagger/ReDoc disabled in production (docs_url=None when DEBUG=False)
- [01-04]: Manual migration used when autogenerate fails (no live DB required)
- [01-04]: alembic.ini sqlalchemy.url overridden by env.py using settings.DATABASE_URL
- [02-01]: JSONB column for extracted_metadata (flexible schema over separate columns)
- [02-01]: python-docx for DOCX text extraction from paragraphs + tables
- [02-01]: Morphological open/close in OCR pipeline for noise removal
- [02-01]: Multi-PSM retry (psm 6 -> psm 3) for sparse OCR results
- [02-02]: Upload returns 202 Accepted with Celery task dispatch (non-blocking)
- [02-02]: Celery progress stages: reading (10%) -> extracting (30%) -> metadata (60%) -> saving (80%)
- [02-02]: Exponential backoff retry: 60s * 2^retries on task failure
- [02-03]: Frontend polls /status every 2.5s after upload completes
- [02-04]: dateutil.parse(fuzzy=True, dayfirst=True) for Indian date formats
- [02-04]: Amount extraction validates 0.01-10M range to filter false positives
- [03-01]: LinearSVC with CalibratedClassifierCV for probability-calibrated SVM classification
- [03-01]: Manual C-value search over nested GridSearchCV for small-class CV stability
- [03-01]: TF-IDF (1,3) ngrams with 15K features and class_weight='balanced' on LR
- [03-01]: Synthetic augmentation factor=10 in combined mode to boost underrepresented categories
- [03-02]: ConfidenceBadge duplicated per-page (not shared component) to minimize file additions
- [03-02]: ML router at /api/ml prefix, separate from /api/documents
- [03-02]: Confusion matrix uses intensity-based red shading for off-diagonal errors
- [Phase 04-search-retrieval]: Stored TSVECTOR column + trigger over functional index to avoid Alembic autogenerate false-diff bug (issue #1390)
- [Phase 04-search-retrieval]: GIN index for search_vector created via op.execute() only (not SQLAlchemy Index in __table_args__) to prevent Alembic false diffs
- [Phase 04-search-retrieval]: FTS with q > 3 char threshold: ILIKE fallback for 1-3 char queries; trigram handles typo tolerance in 04-03
- [Phase 04-search-retrieval]: NULL guard on extracted_metadata: isnot(None) before astext.cast(Float) prevents 500 on docs without amount metadata
- [Phase 04-search-retrieval]: OR-combine (not trigram-only): FTS handles exact/stemmed matches; trigram adds typo tolerance as supplemental path via or_(search_vector @@, extracted_text %)
- [Phase 04-search-retrieval]: pg_trgm threshold 0.3 preserved globally; threshold change from >3 to >2 chars corrects ILIKE fallback boundary so 3-char tokens (UPI, GST) get trigram path
- [05-01]: Fernet key derived from SECRET_KEY via SHA-256 hash (no separate FERNET_KEY env var)
- [05-01]: Lazy SDK imports in provider.py to avoid ImportError when optional SDKs not installed
- [05-01]: Regex fallback with confidence=0.3 when LLM call fails for graceful degradation
- [05-01]: MAX_CHARS=50000 silent truncation to fit within LLM context windows
- [05-01]: Migration 0004 uses op.execute() for index creation consistent with project Alembic pattern
- [05-02]: Composable prompt pattern: BASE_SYSTEM_PROMPT + CATEGORY_HINTS[category] for 6 doc types
- [05-02]: LLM extraction stage is entirely non-fatal in Celery pipeline (broad except catches all)
- [05-02]: 50-char minimum text threshold before attempting LLM extraction
- [05-02]: Celery progress stages now: reading(10%) > extracting(30%) > metadata(50%) > ai(70%) > saving(85%)
- [05-03]: Settings router at /api/settings prefix, separate from /api/documents and /api/ml
- [05-03]: Provider validation via Pydantic regex pattern (gemini|openai|anthropic|local)
- [05-03]: API key only sent to backend when user types new value; blank preserves existing encrypted key
- [05-03]: Decryption failure non-fatal in GET: logged as warning, api_key_set=true, last4=null

### Pending Todos

None.

### Dataset Pipeline (Phase 3 Groundwork)

- 7 Kaggle datasets downloaded (~28 GB raw data) inside Docker container
- Dataset download script: `python -m app.ml.datasets.download`
- Data preparation pipeline: `python -m app.ml.datasets.prepare`
- Training supports 4 modes: auto, synthetic, real, combined
- Combined training: 85.06% accuracy (Linear SVC, 15K vocab, 2,050 samples)
- Per-category: UPI 100%, tickets 100%, tax 95%, bank 79%, bills 72%, invoices 67%
- Achieved >85% target via LinearSVC + augmentation_factor=10 + TF-IDF (1,3) ngrams

### Blockers/Concerns

- Research flagged LLM hallucination risk (69-88%) for Phase 5 -- will need validation with real documents
- ~~Hardcoded SECRET_KEY is a critical security issue to resolve immediately in Phase 1~~ RESOLVED in 01-01
- Rate limiter requires Redis to be running; without Redis, rate limits won't persist across restarts
- ~~No Alembic migrations yet; table creation relies on SQLAlchemy auto-create~~ RESOLVED in 01-04
- ~~New models in future phases must be imported in backend/alembic/env.py for autogenerate to work~~ UserLLMSettings registered in 05-01
- ~~Metadata extraction is regex-based v1~~ Phase 5 LLM extraction service now provides structured extraction with fallback
- ~~ML classifier trained on synthetic data only~~ RESOLVED: real dataset pipeline operational
- Migration 0004 must be applied to database before AI extraction endpoints are used (05-03)

## Session Continuity

Last session: 2026-03-17T11:56:55Z
Stopped at: Completed 05-03-PLAN.md -- LLM settings API and settings page
Resume file: None
