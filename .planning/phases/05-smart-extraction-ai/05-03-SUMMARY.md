---
phase: 05-smart-extraction-ai
plan: 03
subsystem: api, ui
tags: [fastapi, pydantic, nextjs, react, settings, llm-provider, encryption]

# Dependency graph
requires:
  - phase: 05-01
    provides: UserLLMSettings model with encrypt_api_key/decrypt_api_key, get_current_user dependency
provides:
  - GET /api/settings/llm endpoint returning masked LLM config
  - PUT /api/settings/llm endpoint upserting provider and encrypted API key
  - Settings page at /dashboard/settings with 4 provider cards
  - settingsApi in frontend API client
  - Settings link in dashboard sidebar
affects: [05-04, future phases needing provider config UI]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Upsert pattern for per-user settings (query then insert-or-update)"
    - "API key masking: only last 4 chars returned, never full key"
    - "Radio-card provider selection with white border highlight"

key-files:
  created:
    - backend/app/schemas/settings.py
    - backend/app/routers/settings.py
    - frontend/src/app/dashboard/settings/page.tsx
  modified:
    - backend/app/main.py
    - frontend/src/lib/api.ts
    - frontend/src/app/dashboard/layout.tsx

key-decisions:
  - "Provider validation via Pydantic regex pattern (gemini|openai|anthropic|local)"
  - "API key only sent to server when user types a new one; blank input preserves existing key"
  - "Decryption failure logged but does not crash -- api_key_set still true, last4 shown as null"

patterns-established:
  - "Settings router at /api/settings prefix, separate from /api/documents and /api/ml"
  - "Provider card UI: grid of selectable cards with border-white active state"

# Metrics
duration: 4min
completed: 2026-03-17
---

# Phase 5 Plan 3: LLM Settings API & UI Summary

**GET/PUT settings endpoints with encrypted API key storage and 4-provider selection page (Gemini, OpenAI, Anthropic, Local)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-17T11:53:02Z
- **Completed:** 2026-03-17T11:56:55Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Settings API with GET/PUT /api/settings/llm, protected by JWT auth
- API key never returned in full -- only last 4 characters shown via masked response
- Provider validation restricts to gemini, openai, anthropic, or local
- Settings page with 4 radio-style provider cards and configuration form
- settingsApi added to frontend API client
- Settings link added to dashboard sidebar navigation

## Task Commits

Each task was committed atomically:

1. **Task 1: Create settings API with GET/PUT endpoints for LLM configuration** - `09c5798` (feat)
2. **Task 2: Build frontend settings page and add settingsApi** - `c4fd7a0` (feat)

## Files Created/Modified
- `backend/app/schemas/settings.py` - Pydantic schemas for LLM settings request/response
- `backend/app/routers/settings.py` - GET/PUT /api/settings/llm with upsert and key masking
- `backend/app/main.py` - Register settings router
- `frontend/src/lib/api.ts` - Add settingsApi (getLLMSettings, updateLLMSettings)
- `frontend/src/app/dashboard/settings/page.tsx` - Settings page with provider cards and config form
- `frontend/src/app/dashboard/layout.tsx` - Add Settings to sidebar nav

## Decisions Made
- Provider validation via Pydantic regex pattern on LLMSettingsUpdate
- API key only sent to backend when user types a new value; blank preserves existing encrypted key
- Decryption failure in GET is non-fatal: logged as warning, api_key_set remains true, last4 shown as null
- Settings router registered at /api/settings prefix (separate from /api/documents and /api/ml)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Settings API ready for 05-04 (extraction endpoint) to read user's LLM provider config
- Provider selection persisted per-user for extraction pipeline to consume
- API key encrypted at rest using Fernet derived from SECRET_KEY

---
*Phase: 05-smart-extraction-ai*
*Completed: 2026-03-17*
