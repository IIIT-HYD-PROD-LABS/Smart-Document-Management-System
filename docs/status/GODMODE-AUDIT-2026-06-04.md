# GODMODE Sweep, 2026-06-04: Swappable LLM provider, notice upload, page lag, fetch correctness, classification robustness

Opus 4.8 (ultracode) end-to-end sweep. Goal: make the notice-upload feature
work with a swappable LLM provider (Ollama now, GPT-class later), fix page lag
and data-fetch gaps, repair compliance flows, and accept every document type.

## Headline

The notice-upload AI extraction was hard-gated on a per-tenant BYOK key
(Anthropic or Google only). With Ollama there is no key, so the extract path
returned HTTP 412 and "did nothing". Root cause: two parallel LLM stacks. The
generic document extractor (`app/services/llm_service.py`) already supported
Ollama/Gemini/Anthropic/OpenAI via `settings.LLM_PROVIDER`, but the compliance
notice/AI surface (`app/compliance/services/ai_*`) was BYOK-only with no
server-default fallback.

Fix: a single resolver (`ai_service.resolve_credential`) that uses the
per-tenant BYOK key when present, otherwise falls back to a server-default
provider driven by `settings.LLM_PROVIDER`. Ollama and OpenAI adapters were
added to the compliance provider factory. "Ollama now, GPT later" is now a
one-line env change (`LLM_PROVIDER=ollama` to `LLM_PROVIDER=openai` plus
`OPENAI_API_KEY`). Every AI feature (notice extraction, summaries, action
recommendations, response drafting, invoice AI, chat) inherits the fallback
because they all funnel through `_build_active_provider(db, cred)`.

Verified end to end against live Ollama `llama3.2`: a sample income-tax notice
extracted notice_number, authority, dates, tax_demand, and legal_sections as
valid JSON through the real scope-locked prompt.

## Backend changes (orchestrator)

- `app/compliance/services/ai_providers.py`: added `OllamaProvider` (local
  `/api/chat`, no key, SSRF-safe base URL from settings, actionable 404 "pull
  the model" message) and `OpenAIProvider` (official SDK, mirrors the Anthropic
  exception mapping). `build_provider` now supports anthropic, google, ollama,
  openai.
- `app/compliance/services/ai_service.py`: `_server_default_config()` maps
  `settings.LLM_PROVIDER` to (provider, model, key) with per-provider default
  models; `_ServerCredential` synthetic credential; `resolve_credential()`
  (BYOK wins, else server default, else None); `_build_active_provider` skips
  decrypt and `last_used_at` for the synthetic credential.
- `notice_extractor_service.py`, `response_drafter_service.py`,
  `routers/ai.py`: switched from `get_credential` to `resolve_credential`, so
  412 now fires only when neither a tenant key nor a server provider exists.
- `app/compliance/routers/notices.py`: `_read_validated_upload` rewritten to
  accept every type the generic uploader does (pdf, png, jpg, jpeg, tiff, bmp,
  docx), validated by extension (filename first, content-type fallback, null
  bytes stripped) plus magic bytes. Was PDF/JPG/PNG only.
- `.env`: `LLM_PROVIDER=ollama`, `LLM_MODEL=llama3.2` (GEMINI key retained for
  the later switch).

## Classification robustness (sub-agent, app/ml + tasks)

Silent-failure fixes; failures now distinguish operational (retryable) from
genuine empty via a typed `ExtractionEngineError(reason, retryable)` in
`app/ml/errors.py`. `extract_and_classify` keeps its 3-tuple return (callers,
including the notice path, unchanged).

- C1: empty/failed extraction was marked COMPLETED with UNKNOWN. Now a non-txt
  source yielding no text is marked FAILED with `ai_extraction_status="no_text"`.
- H1: Tesseract/OCR engine failure was swallowed to "". Now re-raised as a
  retryable `ExtractionEngineError`.
- H2: missing model artifacts returned silent "unknown". Now raises
  `ExtractionEngineError("model_artifacts_missing")` so the task retries.
- H3: multi-page TIFF lost pages 2+. New frame-iterating TIFF path (cap 200).
- M4: scanned-PDF OCR silently capped at 50 pages. Now surfaces
  `ai_extraction_status="incomplete_scanned_pdf"` (still COMPLETED).
- DOCX: corrupt container raises a non-retryable `ExtractionEngineError`.

## Frontend (two sub-agents + orchestrator UI pass)

Data-fetch correctness:
- Cross-client cache contamination (H4): the review, search, and AI-credential
  React Query keys omitted the active client id, so switching clients served
  the previous tenant's data until staleTime expired. Added `activeClientId` to
  all three keys plus `enabled` gates. Search now uses v5 `keepPreviousData`
  (scoped, so it cannot bleed across a tenant switch).
- Documents list paginated (was capped at 50 with no pagination UI).

Page lag:
- Imperative hover/selection DOM mutations replaced with CSS `:hover` (zero JS
  per mousemove, pixel-identical) across the documents pages.
- `DocumentRow` and admin `UserRow` memoized with stable `useCallback`
  handlers; analytics charts memoized and the theme MutationObserver debounced.

UI (design skills applied: frontend-design, ui-ux-pro-max, impeccable):
- Upload widening: `FileDropzone` and `ExtractionPreviewForm` `accept` maps
  expanded to all document types; copy broadened; inline `role="alert"` error
  state added to the dropzone (was toast-only); `onDropRejected` surfaces an
  unsupported-type message.
- 412 banner reframed: with the server-default provider, a tenant without a key
  still gets AI, so the banner now reads "AI extraction is unavailable right
  now" rather than "connect a provider". AI-settings copy clarifies the
  built-in provider works out of the box and BYOK is optional. Removed an em
  dash from that copy.

## Verification

- Backend: full suite run in memory-bounded chunks against an ephemeral PG15
  (`@db`) + Redis7, `alembic upgrade head`, `GRANT app_runtime`. Result: about
  705 passed, ~32 skipped, 0 failed, 0 errors. New tests:
  `tests/test_ai_provider_resolution.py` (28, resolver + Ollama/OpenAI factory
  + widened upload-ext) and `tests/test_extraction_failures.py` (16).
- Two regressions found and fixed: `test_extract_notice_fields_raises_when_credential_missing`
  asserted the old BYOK-only contract (retargeted to patch `resolve_credential`);
  `test_byok_missing_credential_returns_412` had a pre-existing mock bug (fixed
  `read.return_value` never signalled EOF to the 2026-06-01 streaming-read loop,
  ballooning MagicMock call history; switched to a `side_effect` EOF).
- Real LLM: `OllamaProvider` driven against live `llama3.2` through the actual
  notice prompt returned valid extracted JSON.
- Frontend: `tsc --noEmit` clean across all changes; `next build` succeeds.

## Switching to GPT later

Set in `.env` (or the deploy environment): `LLM_PROVIDER=openai`,
`OPENAI_API_KEY=sk-...`, optionally `LLM_MODEL=gpt-4o-mini`. Restart. No code
change. BYOK (per-tenant Anthropic/Google keys) continues to override the
server default when set.

## Deferred

- M3 (notice detail/response 404-vs-403 disambiguation + select-client-first
  guard): real UX gap, MEDIUM, not actioned this pass.
- Live in-browser walkthrough: every layer below the browser is proven (unit,
  integration, full regression, real-LLM extraction, production build). The
  click-through needs the full stack up against a seeded DB (Supabase
  reachability per the WARP runbook), and the frontend container rebuilt
  (`docker compose build frontend`) since it runs a baked production build.
- Runtime RLS (`DB_ENFORCE_RLS`) remains gated off by design
  (RLS-ACTIVATION-RUNBOOK-2026-06-01).
