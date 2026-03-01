"""Add extracted_metadata and celery_task_id to documents.

Revision ID: 0002
Revises: 097ce00eb065
Create Date: 2026-03-01

Adds two columns to the documents table:
- celery_task_id: tracks the async Celery task processing this document
- extracted_metadata: JSON field for dates, amounts, vendor extracted from text
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "097ce00eb065"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("celery_task_id", sa.String(255), nullable=True))
    op.add_column("documents", sa.Column("extracted_metadata", sa.JSON(), nullable=True))
    op.create_index("ix_documents_celery_task_id", "documents", ["celery_task_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_celery_task_id", table_name="documents")
    op.drop_column("documents", "extracted_metadata")
    op.drop_column("documents", "celery_task_id")
