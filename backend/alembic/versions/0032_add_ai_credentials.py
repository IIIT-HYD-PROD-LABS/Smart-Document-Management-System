"""Add ai_credentials table for BYOK AI integration.

Revision ID: 0032_add_ai_credentials
Revises: 0031_add_client_branding_fields
Create Date: 2026-05-08

Why:
    Client requested an "Ask AI" surface that uses each tenant's own
    Anthropic / Google Gemini API key (BYOK), scoped only to TaxSync
    work (compliance notices, vendor invoices, regulatory deadlines).

    One row per compliance_client (UNIQUE on client_id) — keys are
    organisation-wide, gated by CLIENT_MANAGE_TEAM. The plaintext key
    is never stored: api_key_enc is Fernet ciphertext via the same
    INFRA-06 cipher used for Gmail refresh tokens.

    `provider` is constrained to {'anthropic', 'google'} at the DB level;
    Pydantic enforces the same set at the API boundary. Adding a third
    provider later is one constraint drop + one ORM tuple change.
"""
from alembic import op
import sqlalchemy as sa


revision = "0032_add_ai_credentials"
down_revision = "0031_add_client_branding_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_credentials",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "client_id",
            sa.Integer(),
            sa.ForeignKey("compliance_clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("api_key_enc", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("client_id", name="uq_ai_credentials_client"),
        sa.CheckConstraint(
            "provider IN ('anthropic', 'google')",
            name="ck_ai_credentials_provider",
        ),
    )


def downgrade() -> None:
    op.drop_table("ai_credentials")
