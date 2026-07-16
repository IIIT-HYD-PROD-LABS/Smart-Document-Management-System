"""Add google_drive to documents.source CHECK constraint."""
from alembic import op

revision = "0041_google_drive_source"
down_revision = "0040_audit_logs_rls_policies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_documents_source", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_source",
        "documents",
        "source IN ('manual','gmail','portal','gmail_body','google_drive')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_documents_source", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_source",
        "documents",
        "source IN ('manual','gmail','portal','gmail_body')",
    )
