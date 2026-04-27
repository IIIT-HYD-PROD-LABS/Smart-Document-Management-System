"""Pydantic request/response schemas for Phase 9 compliance APIs.

Modules:
  - client.py    : Client / Registration / Membership / Onboarding / Dashboard
  - notice.py    : Notice CRUD / status transitions / bulk update / filters
  - activity.py  : Notice activity timeline + add-note request

Schemas import the canonical regex/validators from
`app.compliance.utils.indian_validators` so the API boundary enforces the
exact same GSTIN/PAN format as the rest of the system.
"""
