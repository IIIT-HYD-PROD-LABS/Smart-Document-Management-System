"""Phase 15 D-40/D-39: add documents.source provenance column.

Revision ID: 0028_phase15_doc_source_field
Revises: 0027_phase15_recurrence_unique_partial
Create Date: 2026-05-08

Existing rows have no notion of provenance. The /api/documents/all listing
needs to filter Gmail-sourced docs in/out, and the UI surfaces a provenance
badge per row. Add a small ``source`` text column with a CHECK constraint
covering the four supported values:

  - manual      : v1.0 upload endpoint (default for all existing rows)
  - gmail       : Gmail attachment ingested via Phase 15 scanner
  - portal      : Portal scrape ingestion (future Phase)
  - gmail_body  : Synthetic .txt persisted from a Gmail body that matched
                  no filter rule (D-39 — drives v1.0 ML classification on
                  attachment-less emails with >=200 chars of body text).

Index on the column so source-filtered list queries stay sub-100ms when
the documents table grows. Default is intentionally ``manual`` for
existing rows so v1.0 workflows keep their pre-Phase-15 behavior.
"""
from alembic import op
import sqlalchemy as sa


revision = "0028_phase15_doc_source_field"
down_revision = "0027_phase15_recurrence_unique_partial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "source",
            sa.String(length=20),
            nullable=False,
            server_default="manual",
        ),
    )
    op.create_check_constraint(
        "ck_documents_source",
        "documents",
        "source IN ('manual','gmail','portal','gmail_body')",
    )
    op.create_index(
        "ix_documents_source",
        "documents",
        ["source"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_source", table_name="documents")
    op.drop_constraint("ck_documents_source", "documents", type_="check")
    op.drop_column("documents", "source")
