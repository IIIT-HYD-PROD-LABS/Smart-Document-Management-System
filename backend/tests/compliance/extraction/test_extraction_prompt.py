"""Phase 17 EXTRACT-02 — notice extraction prompt module contract.

Plan 17-03 GREEN. The module exposes FIELD_SCHEMA (14 keys) and
build_user_prompt(text). The SYSTEM prompt is reused from Phase 16
(SCOPE_LOCK_SYSTEM), not redefined here — see D-13.
"""
from __future__ import annotations

import pytest

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


def test_extraction_does_not_redefine_system_prompt():
    """D-13: there must NOT be a Phase 17 SYSTEM_PROMPT — extraction reuses Phase 16 scope-lock."""
    import app.compliance.services.notice_extraction_prompt as mod
    assert not hasattr(mod, "SYSTEM_PROMPT"), (
        "D-13 says reuse SCOPE_LOCK_SYSTEM from ai_service; redefining a Phase 17 SYSTEM_PROMPT "
        "would create two scope-lock sources of truth"
    )
