"""SQLAlchemy database engine, session factory, and Base model."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

_connect_args: dict = {}
_db_url = settings.DATABASE_URL
if _db_url.startswith("postgresql") and "localhost" not in _db_url and "127.0.0.1" not in _db_url:
    _connect_args["sslmode"] = "require"

engine = create_engine(
    _db_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=300,
    pool_timeout=30,
    echo=False,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
