"""Fix DateTime timezone and nullable constraints.

Revision ID: 0011_fix_datetime_timezone
Revises: 0010_add_audit_logs
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_fix_datetime_timezone"
down_revision = "0010_add_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix DateTime columns to use timezone-aware timestamps
    # Users
    op.alter_column("users", "created_at", type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column("users", "updated_at", type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column("users", "is_active", nullable=False, existing_type=sa.Boolean(), server_default=sa.text("true"))

    # Documents
    op.alter_column("documents", "created_at", type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column("documents", "updated_at", type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())
    op.alter_column("documents", "confidence_score", nullable=False, existing_type=sa.Float(), server_default=sa.text("0.0"))

    # Document versions
    op.alter_column("document_versions", "created_at", type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())

    # Document permissions
    op.alter_column("document_permissions", "created_at", type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())

    # Audit logs - fix resource_type to allow NULL (model says nullable=True)
    op.alter_column("audit_logs", "resource_type", nullable=True, existing_type=sa.String(50))
    op.alter_column("audit_logs", "created_at", type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())


def downgrade() -> None:
    op.alter_column("audit_logs", "created_at", type_=sa.DateTime(), existing_type=sa.DateTime(timezone=True))
    op.alter_column("audit_logs", "resource_type", nullable=False, existing_type=sa.String(50))
    op.alter_column("document_permissions", "created_at", type_=sa.DateTime(), existing_type=sa.DateTime(timezone=True))
    op.alter_column("document_versions", "created_at", type_=sa.DateTime(), existing_type=sa.DateTime(timezone=True))
    op.alter_column("documents", "confidence_score", nullable=True, existing_type=sa.Float())
    op.alter_column("documents", "updated_at", type_=sa.DateTime(), existing_type=sa.DateTime(timezone=True))
    op.alter_column("documents", "created_at", type_=sa.DateTime(), existing_type=sa.DateTime(timezone=True))
    op.alter_column("users", "is_active", nullable=True, existing_type=sa.Boolean())
    op.alter_column("users", "updated_at", type_=sa.DateTime(), existing_type=sa.DateTime(timezone=True))
    op.alter_column("users", "created_at", type_=sa.DateTime(), existing_type=sa.DateTime(timezone=True))
