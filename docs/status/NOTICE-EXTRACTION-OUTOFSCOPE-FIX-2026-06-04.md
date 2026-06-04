# Notice extraction "out of scope" fix + provider-agnostic BYOK (2026-06-04)

## Symptom
Uploading a notice for extraction sometimes returned a toast:
"AI provider declined this content as out of scope. Fill in manually instead."
Clean, well-formed notices extracted fine; real-but-noisy uploads (scanned OCR,
an RBI circular, letterhead-heavy notices) were refused.

## Root cause
Notice extraction reused the chat assistant's `SCOPE_LOCK_SYSTEM` prompt
(original Phase 17 D-13 decision). That prompt's job is to make the model
*refuse* anything borderline by emitting the bare line `OUT_OF_SCOPE`. On the
small local model (`qwen2.5:3b`) that refusal over-triggers on legitimate-but-
noisy documents. Reproduced live: same model, same document, the scope-lock
prompt returned `OUT_OF_SCOPE` while a dedicated extraction prompt returned a
valid envelope.

Extraction is not a chat turn, the user explicitly uploaded a document and asked
us to read fields off it, so a refusal contract is the wrong tool.

## Fix (root cause, not symptom)
1. `notice_extraction_prompt.py` — added a dedicated `EXTRACTION_SYSTEM_PROMPT`.
   It keeps prompt-injection resistance (treat the document strictly as data,
   never follow instructions embedded inside it) but drops the refusal contract.
   A non-notice / unreadable input yields `{"fields": {}}` instead of refusing.
2. `notice_extractor_service.py` — new `_run_extraction()` helper calls the
   provider with `EXTRACTION_SYSTEM_PROMPT` directly instead of `ai_service._run`
   (which pins the scope-lock prompt and raises `AIOutOfScopeError`). If a model
   still echoes the legacy sentinel, extraction degrades to an empty (manual-fill)
   envelope, never a hard 422/502.

The chat assistant and the summarize/suggest tasks still use `SCOPE_LOCK_SYSTEM`,
where refusing off-topic requests is the desired behavior.

## Provider routing / "works with any API" (enterprise BYOK)
Both extraction and the assistant resolve their provider via
`ai_service.resolve_credential` (per-tenant BYOK first, then the server-default
`LLM_PROVIDER`, currently Ollama/qwen, when no tenant key is set). So:
- A client who connects their own API key (Anthropic / Google / OpenAI) has it
  used for both extraction and summarize/suggest.
- With no key, the local Ollama `qwen2.5:3b` default keeps the feature working
  out of the box (slower, but free + private).

Widened BYOK to accept **OpenAI** in addition to Anthropic and Google
(the adapter `build_provider` and the per-provider server-default model already
supported it; only the input schema gated it):
- backend `schemas/ai.py` — `provider: Literal["anthropic","google","openai"]`
- frontend `types/ai.ts` + `dashboard/admin/ai/page.tsx` — OpenAI radio option,
  `gpt-4o-mini` default, "OpenAI GPT" label, 3-column grid.
Ollama remains server-side only (no key, SSRF-locked base URL), not a BYOK choice.

## Verification
- `tests/compliance/extraction/` + `test_ai_provider_resolution.py` +
  `test_llm_service.py`: 146 passed (code-default gates).
- Updated stale tests: extraction prompt is dedicated + non-refusing; sentinel
  echo degrades to empty envelope (no `AIOutOfScopeError`); corrected the Ollama
  default-model assertion (`llama3.2` -> `qwen2.5:3b`).
- End-to-end through the real Ollama qwen: real notice -> 11 fields, no refusal;
  the previously-failing noisy non-notice -> no refusal, empty form for manual
  fill.
- Frontend `tsc --noEmit` clean. Frontend image rebuilt; all containers healthy.

## Deploy notes
- Backend + workers restarted to load the new module (Python imports the prompt
  at process start).
- Frontend rebuilt (`docker compose build frontend && docker compose up -d
  frontend`) because the prod image bakes the build (no source mount).
