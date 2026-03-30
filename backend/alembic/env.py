"""Alembic migration environment configuration."""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import app settings and Base
from app.config import settings
from app.database import Base

# CRITICAL: Import ALL models so they register with Base.metadata.
# If a model is not imported here, Alembic autogenerate will generate
# a DROP TABLE migration for that model's table.
from app.models.user import User
from app.models.document import Document
from app.models.refresh_token import RefreshToken
from app.models.document_permission import DocumentPermission
from app.models.document_version import DocumentVersion
from app.models.audit_log import AuditLog
_models = (User, Document, RefreshToken, DocumentPermission, DocumentVersion, AuditLog)

config = context.config

# Override sqlalchemy.url from alembic.ini with the app's DATABASE_URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL without connecting)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect to database and execute)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
