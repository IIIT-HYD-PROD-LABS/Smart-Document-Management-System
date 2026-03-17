---
phase: 05-smart-extraction-ai
plan: 02
subsystem: ai, api
tags: [llm, celery, prompts, extraction, gemini, openai, anthropic]

# Dependency graph
requires:
  - phase: 05-01
    provides: UserLLMSettings model, Document AI columns, LLM provider factory, extraction service
provides:
  - Category-specific extraction prompts for 6 document types
  - LLM extraction integrated into Celery document processing pipeline
  - Non-fatal AI extraction stage with graceful degradation
affects: [05-03, 05-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Category-aware prompt templates via CATEGORY_HINTS dict
    - Non-fatal LLM stage in Celery pipeline (broad exception catch)
    - Lazy imports inside task to avoid circular dependencies

key-files:
  created:
    - backend/app/services/llm/prompts.py
  modified:
    - backend/app/services/llm/extraction_service.py
    - backend/app/tasks/document_tasks.py

key-decisions:
  - "Separate BASE_SYSTEM_PROMPT + CATEGORY_HINTS pattern for composable prompts"
  - "LLM extraction stage is entirely non-fatal -- broad except catches all errors"
  - "Text minimum 50 chars before attempting LLM extraction (skip trivially short text)"
  - "Progress percentages redistributed: metadata=50%, ai_extraction=70%, saving=85%"

patterns-established:
  - "Prompt templates: BASE_SYSTEM_PROMPT + CATEGORY_HINTS[category] composable pattern"
  - "Non-fatal pipeline stage: try/except wrapping optional AI step, pipeline continues on failure"

# Metrics
duration: 2min
completed: 2026-03-17
---

# Phase 5 Plan 02: LLM Pipeline Integration Summary

**Category-specific extraction prompts for 6 document types wired into Celery pipeline with non-fatal AI extraction stage**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-17T11:47:56Z
- **Completed:** 2026-03-17T11:50:08Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created extraction prompt templates for all 6 document categories (invoices, bills, tax, bank, tickets, upi) plus generic fallback
- Replaced hardcoded system prompt in extraction service with category-aware `get_extraction_prompt()`
- Wired LLM extraction as Stage 4 in Celery pipeline -- queries UserLLMSettings, calls extract_with_llm, persists results
- LLM failure is completely non-fatal: pipeline continues with regex-only metadata on any error

## Task Commits

Each task was committed atomically:

1. **Task 1: Create document-type-specific extraction prompts and integrate into extraction service** - `aaea885` (feat)
2. **Task 2: Wire LLM extraction into the Celery document processing pipeline** - `5269583` (feat)

## Files Created/Modified
- `backend/app/services/llm/prompts.py` - Category-specific prompt templates with BASE_SYSTEM_PROMPT and CATEGORY_HINTS dict
- `backend/app/services/llm/extraction_service.py` - Updated to use get_extraction_prompt(category) and prefixed user message
- `backend/app/tasks/document_tasks.py` - Added Stage 4 (LLM extraction) with UserLLMSettings lookup and non-fatal error handling

## Decisions Made
- **Composable prompt pattern:** BASE_SYSTEM_PROMPT is shared across all categories; CATEGORY_HINTS dict provides type-specific field lists. Unknown categories get a generic fallback. This keeps prompts maintainable and extensible.
- **Non-fatal LLM stage:** The entire LLM extraction block is wrapped in try/except. If LLM fails (network, auth, timeout, etc.), extraction_status is set to "failed" and the document completes normally with regex-only metadata.
- **50-char minimum:** Documents with less than 50 chars of extracted text skip LLM entirely -- no point burning API tokens on trivially short text.
- **Progress redistribution:** Adjusted from metadata=60%/save=80% to metadata=50%/ai=70%/save=85% to accommodate the new stage.

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None -- no external service configuration required.

## Next Phase Readiness
- LLM extraction is now automatic for users with configured LLM settings
- Ready for 05-03 (API endpoints for LLM settings management and extraction results)
- Ready for 05-04 (frontend integration for AI extraction display)

---
*Phase: 05-smart-extraction-ai*
*Completed: 2026-03-17*
