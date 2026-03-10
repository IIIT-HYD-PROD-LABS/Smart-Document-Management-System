# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-17)

**Core value:** Automated classification and intelligent organization of personal and business documents -- upload any document and the system automatically identifies its type, extracts key data, and makes it instantly searchable.
**Current focus:** Phase 3 complete: ML Classification Upgrade (2/2 plans done). Next: Phase 4

## Current Position

Phase: 3 of 8 (ML Classification Upgrade) -- COMPLETE
Plan: 2 of 2 in current phase
Status: Phase 3 complete -- classifier at 85%, evaluation dashboard live
Last activity: 2026-03-10 -- Phase 3 Plan 2 executed: ML evaluation API + confidence badges + evaluation page

Progress: [██████████░░░░░░░░░░░░░░░░░░░] 10/29 (34%)

## Performance Metrics

**Velocity:**
- Total plans completed: 10
- Average duration: ~8min
- Total execution time: ~84min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation-security-hardening | 4/4 | 41min | 10min |
| 02-document-processing-pipeline | 4/4 | ~24min | ~6min |
| 03-ml-classification-upgrade | 2/2 | 19min | ~10min |

**Recent Trend:**
- Last 5 plans: 02-01 (~6min), 02-02 (~6min), 02-03+04 (~6min), 03-01 (13min), 03-02 (6min)
- Trend: Stable

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

### Pending Todos

None.

### Dataset Pipeline (Phase 3 Groundwork)

- 7 Kaggle datasets downloaded (~19 GB raw data) inside Docker container
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
- New models in future phases must be imported in backend/alembic/env.py for autogenerate to work
- Metadata extraction is regex-based v1 -- Phase 5 LLM will improve accuracy significantly
- ~~ML classifier trained on synthetic data only~~ RESOLVED: real dataset pipeline operational

## Session Continuity

Last session: 2026-03-10
Stopped at: Completed 03-02-PLAN.md -- evaluation dashboard with confidence badges
Resume file: None
