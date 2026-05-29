"""Notice extraction prompt module — Phase 17.

Holds:

  * FIELD_SCHEMA       — the 14-field canonical schema per 17-CONTEXT D-04.
  * build_user_prompt  — assembles the user message that the LLM sees.

The SYSTEM prompt is NOT redefined here — extraction reuses the Phase 16
scope-locked SCOPE_LOCK_SYSTEM directly (D-13). Anything that talks to the
provider must call ai_service._run() OR build a provider and pass
SCOPE_LOCK_SYSTEM explicitly.

Why FIELD_SCHEMA is a dict, not a list:
    The dict keys are the canonical field names the routing gate, the
    validator, and the accept-extraction endpoint all reference. The
    values carry the human-readable hint the prompt embeds so the LLM
    is told what each field means without having to memorise schema
    semantics from the field name alone.
"""
from __future__ import annotations

from typing import Final


# Per 17-CONTEXT.md D-04. Keys MUST match the conftest EXTRACTION_FIELDS
# tuple and the ComplianceNotice column names where canonical notice
# columns exist.
FIELD_SCHEMA: Final[dict[str, str]] = {
    "notice_number": "Authority-issued notice or reference number (e.g. DRC-01/2026/4456, u/s 143(2)).",
    "authority": "Issuing authority. Exactly one of: GST, IT, MCA, RBI, SEBI.",
    "notice_type": "Short label for the notice type (e.g. 'Show Cause Notice u/s 73', 'Scrutiny notice').",
    "issued_date": "Date the notice was issued by the authority. ISO 8601 YYYY-MM-DD.",
    "response_deadline": "Date by which the taxpayer must respond. ISO 8601 YYYY-MM-DD.",
    "tax_demand": "Principal tax amount demanded, in INR. Numeric, no currency symbol.",
    "interest": "Interest amount, in INR. Numeric, no currency symbol.",
    "penalty": "Penalty amount, in INR. Numeric, no currency symbol.",
    "total_liability": "Total amount payable (tax + interest + penalty), in INR.",
    "taxpayer_name": "Legal name of the noticee (the entity the notice is addressed to).",
    "gstin": "15-character GSTIN identifier when present.",
    "pan": "10-character PAN identifier when present.",
    "cin": "21-character Corporate Identification Number when present (MCA).",
    "legal_sections": "List of statutory sections cited (e.g. ['Section 73 of the CGST Act, 2017']).",
}

# Source-text window the extractor sees. The original 4000 (17-CONTEXT D-15)
# silently clipped real notices: letterhead + legal recitals fill the first
# page, so the demand table (tax/interest/penalty/total) and the response
# deadline routinely sat past char 4000 and never reached the model, coming
# back blank. Modern BYOK providers (Gemini 2.5 Flash Lite ~1M tokens, Claude
# ~200k) make a larger window trivial; 24000 chars (~7 pages) covers a single
# notice end to end while staying far under provider input caps.
MAX_TEXT_WINDOW: Final[int] = 24000


def _format_field_list() -> str:
    return "\n".join(f"  - {name}: {hint}" for name, hint in FIELD_SCHEMA.items())


def build_user_prompt(text: str) -> str:
    """Assemble the user message the LLM sees.

    The instructions match 17-CONTEXT D-03 envelope shape and D-05
    precision-over-recall rule (omit unknown fields rather than guess).
    """
    if text is None:
        text = ""
    snippet = text[:MAX_TEXT_WINDOW]
    return f"""\
Extract Indian regulatory compliance notice metadata from the document text below.

For each field you find evidence for, return:
  - "value": the extracted value (use ISO 8601 YYYY-MM-DD for dates, plain numbers without symbols for amounts).
  - "confidence": your 0.0 to 1.0 self-rated certainty.
  - "source_span": the exact substring (max 120 chars) from the document that supports the value.

Fields you may return (omit any field you cannot find evidence for; do NOT guess):
{_format_field_list()}

Return STRICT JSON with no markdown fences, no commentary, no leading whitespace:

{{
  "fields": {{
    "<field_name>": {{ "value": <value>, "confidence": <0.0-1.0>, "source_span": "<substring>" }},
    ...
  }}
}}

Rules:
  - Omit fields you cannot find evidence for. A missing field is better than a wrong one.
  - For `authority`, return exactly one of GST, IT, MCA, RBI, SEBI.
  - For dates, return ISO 8601 (e.g. 2026-05-12). Do NOT return DD-MM-YYYY.
  - For amounts, return plain numbers (e.g. 145000, not "Rs. 1,45,000").
  - For `legal_sections`, return a JSON array of strings.
  - Never wrap the response in ```json fences. Return the JSON object directly.

Document text:
---
{snippet}
---
"""
