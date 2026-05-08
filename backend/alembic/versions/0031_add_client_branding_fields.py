"""Add branding fields to compliance_clients (logo_url, website, address).

Revision ID: 0031_add_client_branding_fields
Revises: 0030_add_user_deleted_at
Create Date: 2026-05-08

Why:
    Client requested an "org details" surface so each tenant can register
    their company name + logo + website + address and have those rendered
    in the product UI (sidebar co-brand cluster, client detail page).

    The data model originally only stored name/client_type/industry/email
    (Phase 9 CLIENT-01). This migration adds the three branding fields.

    `logo_url` is TEXT (not VARCHAR) because the v2.0 implementation stores
    the logo as an inline base64 data URL (`data:image/png;base64,...`).
    Cap is enforced at the API boundary (256 KB pre-encode → ~340 KB on
    the wire). v2.1 may move to filesystem-backed storage if usage warrants
    — at that point this column flips to a /api/.../logo URL string.

    `website` is VARCHAR(255) — Pydantic enforces http(s) prefix at the
    API boundary; we deliberately do not add a DB CHECK so corporate
    redirects and unusual schemes don't trip up onboarding.

    `address` is TEXT to allow multi-line registered-office strings.
"""
from alembic import op
import sqlalchemy as sa


revision = "0031_add_client_branding_fields"
down_revision = "0030_add_user_deleted_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "compliance_clients",
        sa.Column("logo_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "compliance_clients",
        sa.Column("website", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "compliance_clients",
        sa.Column("address", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("compliance_clients", "address")
    op.drop_column("compliance_clients", "website")
    op.drop_column("compliance_clients", "logo_url")
