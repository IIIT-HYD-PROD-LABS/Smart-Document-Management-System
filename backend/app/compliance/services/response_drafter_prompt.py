"""Phase 18 prompt module: build the user prompt for response drafting.

The SYSTEM prompt is NOT redefined here. Phase 18 reuses the Phase 16
SCOPE_LOCK_SYSTEM via `ai_service._run`, so any out-of-scope drift is
rejected by the same OUT_OF_SCOPE sentinel that protects the other AI
surfaces.
"""
from __future__ import annotations

import json
from typing import Any, Final

from app.compliance.models.notice import ComplianceNotice


MAX_GUIDANCE_CHARS: Final[int] = 800
MAX_RESPONSE_TOKENS: Final[int] = 1400


def _notice_context_for_prompt(notice: ComplianceNotice) -> str:
    """Project the notice into a compact JSON the model can read.

    Mirrors `ai_service._notice_context` but trimmed to the fields a
    response drafter actually needs (authority, dates, demands, sections).
    The full extracted_fields payload is also included so the model can
    quote precise statute references when present.
    """
    extracted = notice.extracted_fields or {}
    fields = extracted.get("fields") if isinstance(extracted, dict) else None
    extracted_summary: dict[str, Any] = {}
    if isinstance(fields, dict):
        for name, payload in fields.items():
            if not isinstance(payload, dict):
                continue
            value = payload.get("value")
            if value in (None, ""):
                continue
            extracted_summary[name] = value
    body = {
        "notice_number": notice.notice_number,
        "authority": notice.authority,
        "notice_type": getattr(notice.notice_type, "name", None),
        "received_date": notice.received_date.isoformat()
        if notice.received_date
        else None,
        "response_deadline": notice.response_deadline.isoformat()
        if notice.response_deadline
        else None,
        "tax_demand": str(notice.tax_demand) if notice.tax_demand is not None else None,
        "interest": str(notice.interest) if notice.interest is not None else None,
        "penalty": str(notice.penalty) if notice.penalty is not None else None,
        "total_liability": str(notice.total_liability)
        if notice.total_liability is not None
        else None,
        "legal_sections": list(notice.legal_sections or []),
        "risk_tier": getattr(notice, "risk_tier", None),
        "extracted_fields": extracted_summary,
    }
    return json.dumps(body, indent=2, default=str)


def build_user_prompt(*, notice: ComplianceNotice, user_guidance: str = "") -> str:
    """Assemble the user message the LLM sees.

    The structure mirrors the working Phase 16 prompt pattern: hand the
    model a structured context block, state what kind of output we want,
    and put hard rules near the end so the model treats them as recent.
    """
    guidance = (user_guidance or "").strip()
    guidance_block = (
        f"User guidance for this draft (apply faithfully):\n{guidance}\n"
        if guidance
        else "User guidance for this draft: none provided.\n"
    )
    return f"""\
Draft a formal compliance-notice reply letter for an Indian regulatory authority.
The reply must address every point raised in the notice and present the noticee's position.

Notice context (JSON):
{_notice_context_for_prompt(notice)}

{guidance_block}
Output format:
  - Return PLAIN markdown text. No JSON, no code fences, no preamble.
  - Begin with a subject line "Subject: ..." matching the notice_number.
  - Include addressee, body paragraphs grouped by the points raised, and a
    sign-off block ("Yours faithfully, / [Authorised Signatory] / for
    [Taxpayer Name]").
  - Cite legal sections from `legal_sections` verbatim when present. Do not
    invent sections.
  - For each financial figure (tax, interest, penalty, total) referenced in
    the notice, quote the figure exactly as given. Do not round.
  - Keep the tone professional, terse, and statute-anchored. No marketing
    voice, no apologetics, no negotiation.
  - Length 300 to 700 words.

Rules:
  - Do not fabricate facts not present in the notice context or guidance.
  - Do not advise illegal action.
  - If the notice context is insufficient to draft a competent reply,
    return exactly "INSUFFICIENT_CONTEXT" with no other text.
"""
