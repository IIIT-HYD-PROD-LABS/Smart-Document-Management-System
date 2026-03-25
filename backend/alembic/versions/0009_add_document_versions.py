"""Add document_versions table and current_version column to documents.

Revision ID: 0009_add_document_versions
Revises: 0008_add_highlighted_text
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_add_document_versions"
down_revision = "0008_add_highlighted_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=True),
        sa.Column("s3_url", sa.String(1000), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extracted_metadata", sa.JSON(), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("ai_extracted_fields", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("highlighted_text", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("change_reason", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "version_number", name="uq_document_version"),
    )
    op.create_index("idx_doc_versions_document", "document_versions", ["document_id"])

    op.add_column("documents", sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("documents", "current_version")
    op.drop_index("idx_doc_versions_document", table_name="document_versions")
    op.drop_table("document_versions")
