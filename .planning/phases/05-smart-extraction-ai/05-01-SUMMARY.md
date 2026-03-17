---
phase: 05-smart-extraction-ai
plan: 01
subsystem: ai, database
tags: [instructor, llm, gemini, openai, anthropic, pydantic, fernet, extraction]

# Dependency graph
requires:
  - phase: 02-document-processing-pipeline
    provides: extracted_metadata JSON column, metadata_extractor regex module
  - phase: 04-search-retrieval
    provides: migration 0003 (down_revision for 0004), search_vector column
provides:
  - UserLLMSettings model with encrypted API key storage
  - Document model AI columns (ai_summary, ai_extracted_data, extraction_status)
  - Migration 0004 (user_llm_settings table + document AI columns)
  - LLM provider factory (Gemini, OpenAI, Anthropic via instructor)
  - Pydantic extraction schemas (ExtractedField, DocumentExtraction)
  - Extraction service with LLM call + regex fallback
affects: [05-smart-extraction-ai/05-02, 05-smart-extraction-ai/05-03, 05-smart-extraction-ai/05-04]

# Tech tracking
tech-stack:
  added: [instructor, openai, anthropic, google-generativeai, tiktoken, cryptography]
  patterns: [instructor structured output, Fernet symmetric encryption, lazy SDK imports, regex fallback]

key-files:
  created:
    - backend/app/models/user_settings.py
    - backend/app/services/llm/__init__.py
    - backend/app/services/llm/schemas.py
    - backend/app/services/llm/provider.py
    - backend/app/services/llm/extraction_service.py
    - backend/alembic/versions/0004_add_ai_extraction_fields.py
  modified:
    - backend/app/models/document.py
    - backend/app/models/user.py
    - backend/app/models/__init__.py
    - backend/alembic/env.py
    - backend/requirements.txt

key-decisions:
  - "Fernet key derived from SECRET_KEY via SHA-256 hash (no separate env var needed)"
  - "Lazy SDK imports in provider.py to avoid ImportError when optional SDKs not installed"
  - "Regex fallback with confidence=0.3 when LLM call fails for graceful degradation"
  - "MAX_CHARS=50000 silent truncation to fit within LLM context windows"

patterns-established:
  - "Provider factory pattern: get_llm_client() returns (instructor_client, model_string)"
  - "Extraction schema pattern: ExtractedField with value/confidence/source_hint"
  - "LLM fallback pattern: try LLM -> catch Exception -> regex fallback with lower confidence"

# Metrics
duration: 4min
completed: 2026-03-17
---

# Phase 5 Plan 01: LLM Extraction Foundation Summary

**UserLLMSettings model with Fernet-encrypted API keys, instructor-based provider factory for Gemini/OpenAI/Anthropic, and extraction service with structured Pydantic output and regex fallback**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-17T11:41:17Z
- **Completed:** 2026-03-17T11:45:03Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- UserLLMSettings model with Fernet encryption derived from SECRET_KEY for per-user API key storage
- Document model extended with ai_summary, ai_extracted_data, and extraction_status columns
- Migration 0004 with full upgrade/downgrade for both new table and new columns
- LLM provider factory supporting Gemini (gemini-2.0-flash), OpenAI (gpt-4o-mini), and Anthropic (claude-haiku-4-5-20251001) via instructor library
- Pydantic schemas (ExtractedField, DocumentExtraction) for structured LLM output with confidence scores
- Extraction service with automatic regex fallback using existing metadata_extractor

## Task Commits

Each task was committed atomically:

1. **Task 1: Create UserLLMSettings model, extend Document model, and write migration 0004** - `8e0ad11` (feat)
2. **Task 2: Build LLM provider factory, extraction schemas, and extraction service** - `7ccb758` (feat)

## Files Created/Modified
- `backend/app/models/user_settings.py` - UserLLMSettings model with Fernet encrypt/decrypt methods
- `backend/app/models/document.py` - Added ai_summary, ai_extracted_data, extraction_status columns
- `backend/app/models/user.py` - Added llm_settings relationship
- `backend/app/models/__init__.py` - Registered UserLLMSettings in exports
- `backend/alembic/env.py` - Registered UserLLMSettings for Alembic autogenerate
- `backend/alembic/versions/0004_add_ai_extraction_fields.py` - Migration for AI extraction schema
- `backend/app/services/llm/__init__.py` - Package exports (extract_with_llm, get_llm_client)
- `backend/app/services/llm/schemas.py` - ExtractedField and DocumentExtraction Pydantic models
- `backend/app/services/llm/provider.py` - Provider factory with lazy SDK imports
- `backend/app/services/llm/extraction_service.py` - Core extraction with LLM call + regex fallback
- `backend/requirements.txt` - Added instructor, openai, anthropic, google-generativeai, tiktoken, cryptography

## Decisions Made
- Fernet encryption key derived from SECRET_KEY via SHA-256 (avoids separate FERNET_KEY env var)
- All LLM SDK imports are lazy (inside function body) so the app doesn't crash when optional SDKs are missing
- Regex fallback assigns confidence=0.3 to all fields (distinguishable from LLM's typically higher scores)
- Text truncated at 50K chars to stay within all providers' context windows
- Migration uses op.execute() for index creation consistent with project's Alembic pattern

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. LLM API keys are configured per-user at runtime via the UserLLMSettings model.

## Next Phase Readiness
- Foundation models and services ready for 05-02 (API endpoints for extraction and settings)
- Provider factory ready for 05-03 (Celery async extraction task integration)
- Extraction schemas ready for 05-04 (frontend extraction UI)
- Migration 0004 must be applied before any AI extraction features are used

---
*Phase: 05-smart-extraction-ai*
*Completed: 2026-03-17*
