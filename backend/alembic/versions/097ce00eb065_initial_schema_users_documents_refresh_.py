"""initial schema - users, documents, refresh_tokens

Revision ID: 097ce00eb065
Revises:
Create Date: 2026-02-25 01:16:44.701148

This is the initial migration capturing the complete existing schema.
- Fresh database: run 'alembic upgrade head' to create all tables.
- Existing database (created by Base.metadata.create_all): run 'alembic stamp head'
  to mark the database as current WITHOUT executing any SQL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '097ce00eb065'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    # --- users table ---
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=200), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # --- documents table ---
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('original_filename', sa.String(length=500), nullable=False),
        sa.Column('file_type', sa.String(length=20), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(length=1000), nullable=True),
        sa.Column('s3_url', sa.String(length=1000), nullable=True),
        sa.Column(
            'category',
            sa.Enum('bills', 'upi', 'tickets', 'tax', 'bank', 'invoices', 'unknown',
                    name='documentcategory'),
            nullable=False,
        ),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column(
            'status',
            sa.Enum('pending', 'processing', 'completed', 'failed',
                    name='documentstatus'),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_documents_id'), 'documents', ['id'], unique=False)
    op.create_index(op.f('ix_documents_user_id'), 'documents', ['user_id'], unique=False)
    op.create_index(op.f('ix_documents_category'), 'documents', ['category'], unique=False)
    op.create_index(op.f('ix_documents_status'), 'documents', ['status'], unique=False)
    op.create_index('idx_documents_category_user', 'documents', ['category', 'user_id'], unique=False)
    op.create_index('idx_documents_created_at', 'documents', ['created_at'], unique=False)

    # --- refresh_tokens table ---
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('token', sa.String(length=500), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('replaced_by', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_refresh_tokens_token'), 'refresh_tokens', ['token'], unique=True)
    op.create_index('idx_refresh_tokens_user_id', 'refresh_tokens', ['user_id'], unique=False)
    op.create_index('idx_refresh_tokens_expires', 'refresh_tokens', ['expires_at'], unique=False)


def downgrade() -> None:
    # --- refresh_tokens ---
    op.drop_index('idx_refresh_tokens_expires', table_name='refresh_tokens')
    op.drop_index('idx_refresh_tokens_user_id', table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_token'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')

    # --- documents ---
    op.drop_index('idx_documents_created_at', table_name='documents')
    op.drop_index('idx_documents_category_user', table_name='documents')
    op.drop_index(op.f('ix_documents_status'), table_name='documents')
    op.drop_index(op.f('ix_documents_category'), table_name='documents')
    op.drop_index(op.f('ix_documents_user_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_id'), table_name='documents')
    op.drop_table('documents')

    # --- users ---
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
