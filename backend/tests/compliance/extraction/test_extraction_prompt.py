"""Phase 17 EXTRACT-02 — notice extraction prompt module contract.

The module exposes FIELD_SCHEMA (14 keys), build_user_prompt(text), and a
dedicated EXTRACTION_SYSTEM_PROMPT. Extraction NO LONGER reuses the Phase 16
chat scope-lock prompt (the original D-13 plan): that prompt's refusal contract
made small local models emit OUT_OF_SCOPE on legitimate noisy uploads. The
dedicated prompt keeps injection resistance but never refuses — see the module
docstring in notice_extraction_prompt for the full rationale.
"""
from __future__ import annotations


from .conftest import EXTRACTION_FIELDS  # local fixture mirror


def test_prompt_module_exposes_field_schema():
    """D-04: the 14-field schema lives in the prompt module so the routing gate and the prompt agree."""
    from app.compliance.services.notice_extraction_prompt import FIELD_SCHEMA

    declared = set(FIELD_SCHEMA.keys())
    assert declared == set(EXTRACTION_FIELDS), (
        f"D-04 field schema drift: missing={set(EXTRACTION_FIELDS) - declared}, extra={declared - set(EXTRACTION_FIELDS)}"
    )


def test_field_schema_hints_are_non_empty_strings():
    """Every field hint must be a non-empty string. Empty hints would make the LLM guess."""
    from app.compliance.services.notice_extraction_prompt import FIELD_SCHEMA
    for name, hint in FIELD_SCHEMA.items():
        assert isinstance(hint, str) and len(hint.strip()) > 0, f"empty hint for {name}"


def test_build_user_prompt_includes_envelope_instructions():
    """D-03: user prompt must request the envelope shape the service expects to parse."""
    from app.compliance.services.notice_extraction_prompt import build_user_prompt
    body = build_user_prompt("dummy text")
    assert '"fields"' in body, "prompt must request a fields object"
    assert '"value"' in body and '"confidence"' in body and '"source_span"' in body, (
        "prompt must request value/confidence/source_span on each field (D-03)"
    )


def test_build_user_prompt_enumerates_all_fields():
    """The prompt enumerates every FIELD_SCHEMA key so the model knows the surface."""
    from app.compliance.services.notice_extraction_prompt import FIELD_SCHEMA, build_user_prompt
    body = build_user_prompt("dummy text")
    for name in FIELD_SCHEMA:
        assert name in body, f"field {name} must appear in the user prompt"


def test_extraction_system_prompt_is_dedicated_and_non_refusing():
    """Extraction owns a dedicated SYSTEM prompt that does NOT carry the chat
    refusal contract — that contract caused false OUT_OF_SCOPE refusals on real
    notices (2026-06-04). It must still resist prompt injection (treat the doc as
    data) and instruct an empty envelope for non-notices."""
    from app.compliance.services.notice_extraction_prompt import EXTRACTION_SYSTEM_PROMPT
    from app.compliance.services.ai_service import SCOPE_LOCK_SYSTEM

    p = EXTRACTION_SYSTEM_PROMPT
    assert isinstance(p, str) and p.strip(), "extraction system prompt must be a non-empty string"
    assert p != SCOPE_LOCK_SYSTEM, "extraction must NOT reuse the chat scope-lock refusal prompt"
    low = p.lower()
    assert "data" in low and "never follow" in low, "must keep prompt-injection resistance"
    assert "never refuse" in low, "extraction prompt must instruct the model not to refuse"
    assert '{"fields": {}}' in p, "must instruct an empty envelope for non-notice / unreadable input"
