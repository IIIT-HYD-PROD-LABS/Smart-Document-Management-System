# Phase 5: Smart Extraction (AI) - Research

**Researched:** 2026-03-17
**Domain:** LLM-powered structured document extraction with multi-provider abstraction
**Confidence:** HIGH

## Summary

This phase adds LLM-powered extraction to the existing document processing pipeline, replacing the current regex-based `metadata_extractor.py` with intelligent extraction that produces structured fields (dates, amounts, parties, key terms), one-paragraph summaries, and per-field confidence scores. The system must support three provider modes: OpenAI, Anthropic, and local-only (regex fallback or Ollama).

The existing codebase already has the infrastructure this phase needs: Celery async tasks (`document_tasks.py`) with progress reporting, a `Document.extracted_metadata` JSON column, a document detail page that renders metadata, and a Pydantic schema (`DocumentResponse`) that serializes `extracted_metadata`. The primary work is building a provider-abstracted LLM service, defining extraction prompt templates per document type, adding new DB columns for AI summary and extraction status, and building the settings UI for provider selection.

The recommended approach uses the **`instructor`** library (v1.14.x) as the provider abstraction layer. Instructor wraps OpenAI, Anthropic, and Ollama with a single `from_provider()` interface and returns validated Pydantic models directly. This eliminates the need to hand-roll provider switching, JSON parsing, or response validation. For confidence scoring, the LLM itself is prompted to self-assess each extracted field's confidence as part of the structured output schema.

**Primary recommendation:** Use `instructor` (v1.14.x) with `from_provider()` for unified OpenAI/Anthropic/Ollama structured extraction, Pydantic models for extraction schemas with per-field confidence, and integrate into the existing Celery pipeline as an additional processing stage after text extraction.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `instructor` | 1.14.x | Provider-abstracted structured LLM extraction | 3M+ monthly downloads, supports OpenAI/Anthropic/Ollama via single `from_provider()` API, returns validated Pydantic models |
| `openai` | 2.28.x | OpenAI API client (used by instructor internally) | Official SDK, required for `instructor` OpenAI provider |
| `anthropic` | 0.84.x | Anthropic API client (used by instructor internally) | Official SDK, required for `instructor` Anthropic provider |
| `pydantic` | 2.x (already installed via pydantic-settings) | Extraction schema definitions with validation | Already in stack, instructor depends on it for structured output |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `ollama` | latest | Local Ollama client for local-only LLM mode | When user selects "local-only" provider and has Ollama running |
| `tiktoken` | latest | Token counting for OpenAI models | Estimating cost, truncating long documents to fit context windows |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `instructor` | Direct OpenAI/Anthropic SDKs | More code, manual JSON parsing, no unified interface, must hand-roll provider switching |
| `instructor` | `litellm` | LiteLLM is a heavier proxy/gateway, overkill for 3 providers; instructor is lighter and Pydantic-native |
| `instructor` | `pydantic-ai` | Pydantic AI is a full agent framework; heavier than needed for extraction-only use case |
| Self-assessed confidence | Token log-probabilities | Log-probs are provider-specific, not available on Anthropic, harder to normalize; self-assessment is simpler and provider-agnostic |

**Installation:**
```bash
pip install instructor openai anthropic tiktoken
# Optional for local LLM support:
pip install ollama
```

## Architecture Patterns

### Recommended Project Structure
```
app/
├── services/
│   ├── storage_service.py          # (existing)
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── provider.py             # Provider factory: get_client(provider_name) -> instructor client
│   │   ├── extraction_service.py   # Main extraction orchestrator
│   │   ├── prompts.py              # Document-type-specific prompt templates
│   │   └── schemas.py              # Pydantic models for extraction output
│   └── settings_service.py         # CRUD for user LLM settings
├── models/
│   ├── document.py                 # (existing - add ai_summary, extraction_status columns)
│   └── user_settings.py            # New model for per-user LLM provider config
├── routers/
│   ├── documents.py                # (existing - extend for extraction data)
│   └── settings.py                 # New router for LLM provider settings
├── tasks/
│   └── document_tasks.py           # (existing - add LLM extraction stage)
└── schemas/
    ├── document.py                 # (existing - extend response with ai fields)
    └── settings.py                 # New schemas for settings API
```

### Pattern 1: Provider Factory with Instructor
**What:** A factory function that returns an instructor-patched client based on the user's configured provider.
**When to use:** Every LLM call goes through this factory.
**Example:**
```python
# Source: instructor docs - from_provider API
import instructor

def get_llm_client(provider: str, api_key: str | None = None):
    """Return an instructor client for the configured provider."""
    provider_map = {
        "openai": f"openai/{_get_openai_model()}",
        "anthropic": f"anthropic/{_get_anthropic_model()}",
        "ollama": f"ollama/{_get_ollama_model()}",
    }
    provider_string = provider_map.get(provider)
    if not provider_string:
        raise ValueError(f"Unknown provider: {provider}")

    kwargs = {}
    if api_key:
        kwargs["api_key"] = api_key

    return instructor.from_provider(provider_string, **kwargs)
```

### Pattern 2: Pydantic Extraction Schema with Per-Field Confidence
**What:** Structured output model where each extracted field has a companion confidence score.
**When to use:** All LLM extraction calls use this as the `response_model`.
**Example:**
```python
# Source: instructor + Pydantic structured output patterns
from pydantic import BaseModel, Field
from typing import Optional

class ExtractedField(BaseModel):
    """A single extracted value with confidence."""
    value: str | None = None
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score from 0.0 (no confidence) to 1.0 (certain)"
    )

class DocumentExtraction(BaseModel):
    """Complete structured extraction from a document."""
    # Core fields per EXTR-01
    dates: list[ExtractedField] = Field(
        default_factory=list,
        description="Dates found in the document (ISO format YYYY-MM-DD)"
    )
    amounts: list[ExtractedField] = Field(
        default_factory=list,
        description="Monetary amounts with currency symbols"
    )
    parties: list[ExtractedField] = Field(
        default_factory=list,
        description="People, companies, or organizations mentioned"
    )
    key_terms: list[ExtractedField] = Field(
        default_factory=list,
        description="Important clauses, terms, or conditions"
    )

    # Summary per EXTR-03
    summary: str = Field(
        description="One-paragraph summary of the document's content and purpose"
    )

    # Overall extraction confidence
    overall_confidence: float = Field(
        ge=0.0, le=1.0,
        description="Overall confidence in the extraction quality"
    )

    # Document type detected
    document_type: str = Field(
        description="Detected document type (invoice, contract, receipt, letter, etc.)"
    )
```

### Pattern 3: Celery Pipeline Extension
**What:** Add LLM extraction as a new stage in the existing `process_document_task`.
**When to use:** After text extraction (stage 2), before saving results (stage 4).
**Example:**
```python
# Extending existing document_tasks.py
# After extract_and_classify() succeeds:

# Stage 3: LLM extraction (new)
self.update_state(state="PROGRESS", meta={"stage": "ai_extraction", "progress": 50})
try:
    extraction_result = run_llm_extraction(
        text=extracted_text,
        document_type=category,
        user_id=doc.user_id,
        db=db,
    )
    doc.ai_summary = extraction_result.summary
    doc.ai_extracted_data = extraction_result.model_dump()
    doc.extraction_status = "completed"
except LLMProviderError as e:
    logger.warning("llm_extraction_failed", document_id=document_id, error=str(e))
    doc.extraction_status = "failed"
    # Fall back to regex extraction - don't fail the whole task
```

### Pattern 4: Graceful Degradation
**What:** LLM extraction failure never blocks document processing. Falls back to regex extractor.
**When to use:** Always. LLM APIs are external dependencies that can fail.
**Example:**
```python
def run_llm_extraction(text: str, document_type: str, user_id: int, db) -> DocumentExtraction:
    """Attempt LLM extraction with fallback to regex."""
    settings = get_user_llm_settings(user_id, db)

    if settings.provider == "local-only" or not settings.api_key:
        # Use enhanced regex extraction (existing metadata_extractor.py)
        return regex_to_extraction_schema(extract_metadata(text))

    try:
        client = get_llm_client(settings.provider, settings.api_key)
        prompt = get_extraction_prompt(document_type, text)
        result = client.create(
            response_model=DocumentExtraction,
            messages=[{"role": "user", "content": prompt}],
            max_retries=2,
        )
        return result
    except Exception as e:
        logger.warning("llm_fallback_to_regex", error=str(e))
        return regex_to_extraction_schema(extract_metadata(text))
```

### Anti-Patterns to Avoid
- **Blocking the upload on LLM calls:** LLM extraction MUST be async via Celery. Never call LLM APIs synchronously in the request handler.
- **Storing raw LLM responses:** Always validate through Pydantic schema before storing. Never store unvalidated JSON from LLM.
- **Failing document processing on LLM error:** LLM extraction is an enrichment, not a gate. Document should still be "completed" even if LLM fails.
- **Hardcoding model names:** Model names should be configurable, not hardcoded. Store in settings or config.
- **Sending full document text to LLM without truncation:** Documents can exceed context windows. Truncate to fit with buffer for output tokens.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Provider switching (OpenAI/Anthropic/Ollama) | Custom ABC with per-provider adapters | `instructor.from_provider()` | Handles auth, response formats, retry, streaming differences across providers |
| JSON schema enforcement | Manual JSON parsing + regex validation | `instructor` + Pydantic `response_model` | Instructor forces valid Pydantic output; handles retries on malformed responses |
| Token counting / context window management | Character count heuristics | `tiktoken` for OpenAI, model-specific tokenizers | Token count != character count; wrong estimation causes truncated responses or API errors |
| API key encryption at rest | Custom AES encryption | `cryptography.fernet` or database-level encryption | Rolling your own crypto is a security anti-pattern |
| Retry with exponential backoff for LLM APIs | Custom retry loops | `instructor`'s built-in `max_retries` + Celery's `autoretry_for` | Both handle backoff, jitter, and max attempts correctly |
| Confidence scoring | Custom NLP confidence heuristics | LLM self-assessment in structured output schema | Simpler, provider-agnostic, correlates well with extraction quality |

**Key insight:** The `instructor` library solves the three hardest problems at once: provider abstraction, structured output enforcement, and automatic retry on validation failure. Building a custom abstraction layer over OpenAI + Anthropic + Ollama SDKs would be 500+ lines of brittle code that instructor handles in a single function call.

## Common Pitfalls

### Pitfall 1: Context Window Overflow
**What goes wrong:** Document text exceeds the model's context window, causing API errors or silent truncation.
**Why it happens:** PDFs can contain 50K+ tokens of text. GPT-4o-mini has 128K context but output quality degrades with very long inputs.
**How to avoid:** Truncate input text to ~80% of context window, reserving 20% for output tokens. For a 128K model, cap input at ~100K tokens. Use `tiktoken` for accurate counting.
**Warning signs:** API errors mentioning "maximum context length", or extraction quality drops on long documents.

### Pitfall 2: LLM Hallucination of Extracted Fields
**What goes wrong:** LLM invents dates, amounts, or parties that don't exist in the document.
**Why it happens:** LLMs are generative -- they produce plausible-sounding content even when the source document doesn't contain the information.
**How to avoid:** Three strategies:
1. Per-field confidence scores (the LLM rates its own certainty)
2. Instruct the model explicitly: "Only extract information that is explicitly stated in the text. If a field is not found, leave it empty."
3. Post-extraction validation: cross-reference LLM-extracted dates/amounts against regex extraction results from the existing `metadata_extractor.py`
**Warning signs:** Extracted fields have very low confidence scores, or LLM results don't overlap with regex results at all.

### Pitfall 3: API Key Security
**What goes wrong:** User API keys stored in plaintext in the database, exposed in logs, or leaked through API responses.
**Why it happens:** Quick implementation stores keys as plain strings.
**How to avoid:** Encrypt API keys at rest using Fernet symmetric encryption. Never log API keys. Never return full keys in API responses (mask all but last 4 chars). Store encryption key in environment variable, not in code.
**Warning signs:** API keys visible in structured logs, full keys returned in settings GET endpoint.

### Pitfall 4: Rate Limiting and Cost Explosion
**What goes wrong:** Bulk document uploads trigger hundreds of concurrent LLM API calls, hitting rate limits or running up massive costs.
**Why it happens:** Each document upload triggers a Celery task that calls the LLM API.
**How to avoid:** Use Celery's `rate_limit` on the extraction task (e.g., `rate_limit="10/m"` for 10 documents per minute). Add a per-user daily token budget in settings. Log token usage for cost monitoring.
**Warning signs:** 429 errors from LLM providers, unexpected billing spikes.

### Pitfall 5: OpenAI Structured Output Schema Constraints
**What goes wrong:** Pydantic models with `Optional` fields, `default` values, or complex types fail OpenAI's strict schema validation.
**Why it happens:** OpenAI's structured output requires all fields to be `required` in JSON Schema and doesn't support `$ref`, `default`, or certain constraints like `minimum`/`maximum` in the schema itself.
**How to avoid:** Use `instructor` which automatically handles schema transformation for each provider. Define fields as `str | None` instead of `Optional[str]` for nullable fields. Avoid deeply nested or recursive schemas.
**Warning signs:** OpenAI API errors about invalid schema, "additionalProperties" errors.

### Pitfall 6: Blocking Document Processing on LLM Failure
**What goes wrong:** A document is stuck in "processing" forever because the LLM API is down.
**Why it happens:** LLM extraction is treated as a required step rather than an enrichment.
**How to avoid:** Make LLM extraction a separate status field (`extraction_status`). A document can be `status=completed` with `extraction_status=failed`. Always fall back to regex extraction. Set task-level timeouts (e.g., `soft_time_limit=120`).
**Warning signs:** Documents stuck in "processing" status, Celery tasks never completing.

## Code Examples

### Complete Extraction Service
```python
# app/services/llm/extraction_service.py
import instructor
import structlog
from app.services.llm.schemas import DocumentExtraction
from app.services.llm.prompts import get_extraction_prompt
from app.ml.metadata_extractor import extract_metadata

logger = structlog.stdlib.get_logger()

class ExtractionService:
    """Orchestrates LLM-based document extraction with fallback."""

    def __init__(self, provider: str, api_key: str | None = None, model: str | None = None):
        self.provider = provider
        self.api_key = api_key
        self.model = model or self._default_model(provider)

    def _default_model(self, provider: str) -> str:
        defaults = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-haiku-4.5",
            "ollama": "llama3",
        }
        return defaults.get(provider, "gpt-4o-mini")

    def _get_client(self):
        provider_string = f"{self.provider}/{self.model}"
        kwargs = {}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        return instructor.from_provider(provider_string, **kwargs)

    def extract(self, text: str, document_type: str) -> DocumentExtraction:
        """Run LLM extraction, falling back to regex on failure."""
        if self.provider == "local-only" or not self.api_key:
            return self._regex_fallback(text)

        # Truncate text to avoid context window overflow
        truncated = text[:50000]  # ~12K tokens conservative estimate

        try:
            client = self._get_client()
            prompt = get_extraction_prompt(document_type, truncated)
            result = client.create(
                response_model=DocumentExtraction,
                messages=[
                    {"role": "system", "content": "You are a document data extraction specialist. Extract only information explicitly present in the text."},
                    {"role": "user", "content": prompt},
                ],
                max_retries=2,
            )
            logger.info("llm_extraction_success", provider=self.provider, doc_type=document_type)
            return result
        except Exception as e:
            logger.warning("llm_extraction_failed_fallback", error=str(e), provider=self.provider)
            return self._regex_fallback(text)

    def _regex_fallback(self, text: str) -> DocumentExtraction:
        """Convert regex extraction to DocumentExtraction schema."""
        meta = extract_metadata(text)
        from app.services.llm.schemas import ExtractedField
        return DocumentExtraction(
            dates=[ExtractedField(value=d, confidence=0.6) for d in meta.get("dates", [])],
            amounts=[ExtractedField(value=f"{a['currency']} {a['amount']}", confidence=0.7) for a in meta.get("amounts", [])],
            parties=[ExtractedField(value=meta["vendor"], confidence=0.4)] if meta.get("vendor") else [],
            key_terms=[],
            summary="AI summary not available. Document processed with local extraction only.",
            overall_confidence=0.5,
            document_type="unknown",
        )
```

### Extraction Prompt Template
```python
# app/services/llm/prompts.py

EXTRACTION_SYSTEM_PROMPT = """You are a document data extraction specialist. Your job is to extract structured information from document text.

Rules:
1. Only extract information EXPLICITLY stated in the text
2. If a field is not found in the text, leave it empty (null/empty list)
3. Rate your confidence for each extracted field from 0.0 to 1.0
4. For dates, use ISO format (YYYY-MM-DD)
5. For amounts, include the currency symbol or code
6. The summary should be exactly one paragraph, 2-4 sentences"""

def get_extraction_prompt(document_type: str, text: str) -> str:
    type_hints = {
        "invoices": "Focus on: invoice number, date, total amount, line items, vendor/seller, buyer.",
        "bills": "Focus on: billing period, due date, total amount, service provider, account number.",
        "tax": "Focus on: tax year, filing date, total income, tax amount, taxpayer name.",
        "bank": "Focus on: transaction dates, amounts, account holder, balance, bank name.",
        "tickets": "Focus on: event/travel date, ticket number, passenger/attendee, price, venue/route.",
        "upi": "Focus on: transaction date, amount, sender, receiver, UPI reference.",
    }
    hint = type_hints.get(document_type, "Extract all relevant dates, amounts, parties, and key terms.")

    return f"""Extract structured data from this {document_type} document.

{hint}

--- DOCUMENT TEXT ---
{text}
--- END DOCUMENT TEXT ---

Extract all relevant fields with confidence scores. Write a one-paragraph summary."""
```

### User Settings Model
```python
# app/models/user_settings.py
from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

class UserLLMSettings(Base):
    __tablename__ = "user_llm_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    llm_provider = Column(String(50), default="local-only", nullable=False)
    # Choices: "openai", "anthropic", "ollama", "local-only"

    api_key_encrypted = Column(Text, nullable=True)
    # Encrypted with Fernet; NULL for local-only/ollama

    model_name = Column(String(100), nullable=True)
    # e.g., "gpt-4o-mini", "claude-haiku-4.5", "llama3"

    ollama_base_url = Column(String(500), default="http://localhost:11434", nullable=True)

    user = relationship("User", backref="llm_settings", uselist=False)
```

### Settings API Endpoint
```python
# app/routers/settings.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.user_settings import UserLLMSettings
from app.utils.security import get_current_user

router = APIRouter(prefix="/api/settings", tags=["Settings"])

@router.get("/llm")
def get_llm_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings = db.query(UserLLMSettings).filter(
        UserLLMSettings.user_id == current_user.id
    ).first()
    if not settings:
        return {"provider": "local-only", "model_name": None, "has_api_key": False}
    return {
        "provider": settings.llm_provider,
        "model_name": settings.model_name,
        "has_api_key": bool(settings.api_key_encrypted),
        "ollama_base_url": settings.ollama_base_url,
    }

@router.put("/llm")
def update_llm_settings(
    data: dict,  # Use a proper Pydantic schema in implementation
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Encrypt API key, validate provider, save to DB
    ...
```

### Database Migration (New Columns)
```python
# alembic/versions/0004_add_ai_extraction_fields.py
def upgrade() -> None:
    # Add AI-specific columns to documents table
    op.add_column("documents", sa.Column("ai_summary", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("ai_extracted_data", sa.JSON(), nullable=True))
    op.add_column("documents", sa.Column("extraction_status", sa.String(50), nullable=True))

    # Create user_llm_settings table
    op.create_table(
        "user_llm_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("llm_provider", sa.String(50), default="local-only", nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("ollama_base_url", sa.String(500), nullable=True),
    )
    op.create_index("ix_user_llm_settings_user_id", "user_llm_settings", ["user_id"])
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `json_mode` (OpenAI) | `response_format` with strict JSON Schema + Pydantic | 2024 Q3 | 100% schema adherence, no more parsing failures |
| Manual provider adapters | `instructor.from_provider()` unified interface | 2025 | Single API for OpenAI/Anthropic/Ollama, no custom wrapper code |
| Token log-probs for confidence | Self-assessed confidence in structured output | 2025 | Provider-agnostic, simpler to implement, works with all models |
| LangChain for extraction | Instructor or direct SDK structured output | 2025-2026 | Lighter weight, fewer dependencies, better debugging |
| OpenAI `chat.completions.create` | OpenAI Responses API (`responses.create`) | 2025 | New API surface, but `chat.completions` still fully supported |

**Deprecated/outdated:**
- `json_mode` (`response_format: {"type": "json_object"}`): Still works but only guarantees valid JSON, not schema compliance. Use strict structured output instead.
- `openai.ChatCompletion` (v0.x): Replaced by `openai.chat.completions` in v1.x+. The v0.x API is completely removed.
- Manual JSON regex parsing of LLM output: Fragile and error-prone. Structured outputs eliminate this entirely.

## Open Questions

1. **Re-extraction of existing documents**
   - What we know: Documents uploaded before Phase 5 have only regex-extracted metadata
   - What's unclear: Should there be a bulk re-extraction feature for existing documents?
   - Recommendation: Defer to Phase 5 implementation. Add a "Re-extract with AI" button on document detail page for individual documents first. Bulk re-extraction can be a follow-up feature.

2. **Token usage tracking and cost visibility**
   - What we know: OpenAI charges $0.15/1M input + $0.60/1M output tokens (gpt-4o-mini). Anthropic charges $1/1M input + $5/1M output (Haiku 4.5).
   - What's unclear: Should we track and display per-document and cumulative token costs to users?
   - Recommendation: Log token usage in structured logs (input_tokens, output_tokens, provider, model). Display cumulative usage on settings page. Implement this as a nice-to-have within the phase.

3. **Ollama model availability detection**
   - What we know: Ollama runs locally and models must be pulled before use.
   - What's unclear: Should the settings page verify Ollama is running and the selected model is available?
   - Recommendation: Add a "Test Connection" button on the settings page that hits the Ollama API. If Ollama is not running or model not pulled, show a helpful error.

4. **Extraction schema versioning**
   - What we know: The `ai_extracted_data` JSON column stores the full Pydantic model dump.
   - What's unclear: If the schema evolves, how do we handle documents extracted with an older schema?
   - Recommendation: Include a `schema_version` field in the extracted data JSON. Frontend renders based on version. V1 is the initial schema.

## Sources

### Primary (HIGH confidence)
- [OpenAI Structured Outputs docs](https://developers.openai.com/api/docs/guides/structured-outputs) - Pydantic parse helper, response_format, schema constraints
- [Anthropic Structured Outputs docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) - `messages.parse()` with output_format, supported models
- [Instructor library docs](https://python.useinstructor.com/) - `from_provider()` API, multi-provider support, version 1.14.x
- [Instructor PyPI](https://pypi.org/project/instructor/) - Version 1.14.5, Python 3.9+
- [Ollama Structured Outputs docs](https://docs.ollama.com/capabilities/structured-outputs) - format parameter, OpenAI-compatible API
- [OpenAI Python SDK GitHub](https://github.com/openai/openai-python) - v2.28.x, `chat.completions.parse()` API
- [Anthropic Python SDK PyPI](https://pypi.org/project/anthropic/) - v0.84.x

### Secondary (MEDIUM confidence)
- [OpenAI API Pricing](https://developers.openai.com/api/docs/pricing/) - GPT-4o-mini: $0.15/1M input, $0.60/1M output
- [Anthropic API Pricing](https://platform.claude.com/docs/en/about-claude/pricing) - Haiku 4.5: $1/1M input, $5/1M output
- [Celery retry/backoff best practices](https://www.vintasoftware.com/blog/celery-wild-tips-and-tricks-run-async-tasks-real-world) - autoretry_for, retry_backoff, acks_late
- [LiteLLM docs](https://docs.litellm.ai/docs/) - Evaluated as alternative, heavier than instructor for this use case

### Tertiary (LOW confidence)
- WebSearch results on LLM hallucination rates (69-88%) for document extraction - validates the need for confidence scoring
- WebSearch results on Pydantic AI as alternative - appears viable but heavier than instructor for extraction-only

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - instructor, openai, anthropic are all well-documented with verified APIs and current versions
- Architecture: HIGH - patterns based on existing codebase analysis (Celery, Document model, metadata_extractor) combined with verified library APIs
- Pitfalls: HIGH - context window limits, hallucination, schema constraints all documented in official sources; API key security is standard practice
- Code examples: MEDIUM - patterns synthesized from official docs and codebase analysis, not copy-pasted from a single verified source

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (30 days - stable ecosystem, library versions may bump minor)
